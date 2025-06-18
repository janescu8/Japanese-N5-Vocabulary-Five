import random
import streamlit as st
import re
import os
import time
import importlib
from gtts import gTTS
from openai import OpenAI

# 初始化 OpenAI client
client = OpenAI(api_key=st.secrets["openai_api_key"])

# 要載入的檔名清單
book_names = [
    "may_25_a",
    "may_29_a",
    "jun_02_a",
]

# 動態匯入並建立 book_options 字典
book_options = {
    name: importlib.import_module(name).word_data for name in book_names
}


# UI
st.title("📚 日文單字遊戲 / English Vocabulary Game")
selected_book = st.selectbox("請選擇一本書 / Choose a book:", list(book_options.keys()))
word_data = book_options[selected_book]
st.write(f"📖 單字庫總數 / Total words: {len(word_data)}")

num_questions = st.number_input("輸入測試題數 / Number of questions:", min_value=1, max_value=len(word_data), value=10, step=1)
test_type = st.radio("請選擇測試類型 / Choose test type:", ["拼寫測試 / Spelling", "填空測試 / Fill-in-the-blank", "單字造句 / Sentence creation"])

# 工具函式
def get_unique_words(n):
    all_words = [(w, d[0], d[1]) for w, d in word_data.items()]
    random.shuffle(all_words)
    return all_words[:n]

def mask_word(sentence, word):
    return sentence.replace(word, "◯" * len(word))

def play_pronunciation(text, mp3="pronunciation.mp3"):
    """Generate and play pronunciation audio in MP3 format."""
    tts = gTTS(text=text, lang="ja")
    tts.save(mp3)
    if os.path.exists(mp3):
        with open(mp3, "rb") as f:
            st.audio(f.read(), format="audio/mp3")

def clean_text(t):
    return re.sub(r'[^a-zA-Z\-’\'\u3040-\u30ff\u4e00-\u9faf\u3000 ]', '', t).lower().strip()

# 初始化狀態
if (
    "initialized" not in st.session_state
    or st.session_state.selected_book != selected_book
    or st.session_state.num_questions != num_questions
):
    st.session_state.words = get_unique_words(num_questions)
    st.session_state.current_index = 0
    st.session_state.score = 0
    st.session_state.mistakes = []
    st.session_state.submitted = False
    st.session_state.input_value = ""
    st.session_state.initialized = True

st.session_state.selected_book = selected_book
st.session_state.num_questions = num_questions
st.session_state.test_type = test_type

# 顯示題目
if st.session_state.current_index < len(st.session_state.words):
    test_word, meaning, example_sentence = st.session_state.words[st.session_state.current_index]
    st.write(f"🔍 提示 / Hint: {meaning}")

    if st.button("播放發音 🎵 / Play Pronunciation"):
        play_pronunciation(test_word if test_type != "填空測試 / Fill-in-the-blank" else example_sentence)

    if test_type.startswith("拼寫測試"):
        user_answer = st.text_input("請輸入單字的正確拼寫 / Enter the correct spelling:", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")
    elif test_type.startswith("填空測試"):
        st.write(f"請填空 / Fill in the blank: {mask_word(example_sentence, test_word)}")
        user_answer = st.text_input("請填入缺漏的單字 / Enter the missing word:", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")
    elif test_type.startswith("單字造句"):
        st.markdown("## ✍️ 請用這個單字造句 / Make a sentence with this word")
        user_answer = st.text_area("輸入你的句子 / Enter your sentence:", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")

    if st.button("提交答案 / Submit Answer"):
        st.session_state.input_value = user_answer
        st.session_state.submitted = True

    if st.session_state.submitted:
        if test_type.startswith("拼寫測試") or test_type.startswith("填空測試"):
            if clean_text(user_answer) == clean_text(test_word):
                st.success("✅ 正確！Correct!")
                st.session_state.score += 1
            else:
                st.error(f"❌ 錯誤 / Incorrect. 正確答案 / Correct answer: {test_word}")
                play_pronunciation(test_word)
                if (test_word, meaning, example_sentence) not in st.session_state.mistakes:
                    st.session_state.mistakes.append((test_word, meaning, example_sentence))

        elif test_type.startswith("單字造句"):
            if not user_answer.strip():
                st.warning("請輸入句子 / Please enter a sentence")
                st.stop()

            with st.spinner("評分中 / Scoring..."):
                prompt = f"""請幫我評分以下英文句子，並提供回饋：\n目標單字：{test_word}\n使用者造的句子：{user_answer}\n\n請提供以下資訊：\n1. 分數（1～10 分）\n2. 評論：是否文法正確？是否有語意問題？是否正確使用該單字？\n3. 建議修正版句子（如果需要）\n"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = response.choices[0].message.content
                    st.markdown("### 📝 評分與回饋 / Feedback")
                    st.write(result)
                    st.session_state.score += 1
                except Exception:
                    st.error("⚠️ OpenAI API 請求過於頻繁或配額已用盡，請稍後再試！/ API limit reached or too many requests. Please try again later!")
                    st.stop()

        st.session_state.input_value = ""

        if st.button("👉 下一題 / Next Question"):
            st.session_state.submitted = False
            st.session_state.current_index += 1
            st.rerun()

# 測驗結束
else:
    st.write(f"🎉 測試結束 / Test Finished! 共回答 / Total questions: {len(st.session_state.words)}")

    if st.session_state.mistakes and not test_type.startswith("單字造句"):
        st.write("❌ 你答錯的單字 / Your Mistakes:")
        for word, meaning, example in st.session_state.mistakes:
            st.write(f"**{word}** - {meaning}")
            st.write(f"例句 / Example: {example}")
            st.write("---")

    if st.button("🔄 重新開始 / Restart"):
        st.session_state.words = get_unique_words(num_questions)
        st.session_state.current_index = 0
        st.session_state.score = 0
        st.session_state.mistakes = []
        st.session_state.submitted = False
        st.session_state.input_value = ""
        st.rerun()
