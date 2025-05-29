import random
import streamlit as st
import re
import os
import time
from gtts import gTTS
from pydub import AudioSegment
from openai import OpenAI

# 初始化 OpenAI client（新版 API）
client = OpenAI(api_key=st.secrets["openai_api_key"])

# 匯入所有書籍的單字庫
from may_25_a import word_data as may_25_a
from may_29_a import word_data as may_29_a

# 書籍選擇
book_options = {
    "may_25_a": may_25_a,
    "may_29_a": may_29_a,
}

# 標題與選書
st.title("📚 日文單字測試遊戲")
selected_book = st.selectbox("請選擇一本書：", list(book_options.keys()))
word_data = book_options[selected_book]
st.write(f"📖 單字庫總數：{len(word_data)} 個單字")

# 題數與測驗類型
num_questions = st.number_input("輸入測試題數", min_value=1, max_value=len(word_data), value=10, step=1)
test_type = st.radio("請選擇測試類型：", ["拼寫測試", "填空測試", "單字造句"])

# 工具函式
def get_unique_words(n):
    all_words = [(w, d[0], d[1]) for w, d in word_data.items()]
    random.shuffle(all_words)
    return all_words[:n]

# 隱藏單字
def mask_word(sentence, word):
    return sentence.replace(word, "◯" * len(word))

def play_pronunciation(text, mp3="pronunciation.mp3", wav="pronunciation.wav"):
    tts = gTTS(text=text, lang='ja')
    tts.save(mp3)
    AudioSegment.from_mp3(mp3).export(wav, format="wav")
    if os.path.exists(wav):
        with open(wav, "rb") as f:
            st.audio(f, format="audio/wav")

def clean_text(t):
    return re.sub(r'[^a-zA-Z\-’\'\u3040-\u30ff\u4e00-\u9faf\u3000 ]', '', t).lower().strip()

# 初始化狀態，只在選書或題數變更時才重新抽題
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

# 每次都更新目前測驗類型（不影響抽題）
st.session_state.selected_book = selected_book
st.session_state.num_questions = num_questions
st.session_state.test_type = test_type

# 顯示題目
if st.session_state.current_index < len(st.session_state.words):
    test_word, meaning, example_sentence = st.session_state.words[st.session_state.current_index]
    st.write(f"🔍 提示：{meaning}")

    if st.button("播放發音 🎵"):
        play_pronunciation(test_word if test_type != "填空測試" else example_sentence)

    if test_type == "拼寫測試":
        user_answer = st.text_input("請輸入單字的正確拼寫：", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")
    elif test_type == "填空測試":
        st.write(f"請填空：{mask_word(example_sentence, test_word)}")
        user_answer = st.text_input("請填入缺漏的單字：", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")
    elif test_type == "單字造句":
        st.markdown("## ✍️ 請用這個單字造句")
        user_answer = st.text_area("輸入你的句子：", value=st.session_state.input_value, key=f"input_{st.session_state.current_index}")

    if st.button("提交答案"):
        st.session_state.input_value = user_answer  # 🔸 這一行加進來
        st.session_state.submitted = True

    if st.session_state.submitted:
        if test_type in ["拼寫測試", "填空測試"]:
            if clean_text(user_answer) == clean_text(test_word):
                st.success("✅ 正確！")
                st.session_state.score += 1
            else:
                st.error(f"❌ 錯誤，正確答案是 {test_word}")
                play_pronunciation(test_word)
                if (test_word, meaning, example_sentence) not in st.session_state.mistakes:
                    st.session_state.mistakes.append((test_word, meaning, example_sentence))

    
        elif test_type == "單字造句":
            if not user_answer.strip():
                st.warning("請輸入句子")
                st.stop()
    
            with st.spinner("評分中..."):
                prompt = f"""請幫我評分以下英文句子，並提供回饋：
    目標單字：{test_word}
    使用者造的句子：{user_answer}
    
    請提供以下資訊：
    1. 分數（1～10 分）
    2. 評論：是否文法正確？是否有語意問題？是否正確使用該單字？
    3. 建議修正版句子（如果需要）
    """
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = response.choices[0].message.content
                    st.markdown("### 📝 評分與回饋")
                    st.write(result)
                    st.session_state.score += 1
                except Exception:
                    st.error("⚠️ OpenAI API 請求過於頻繁或配額已用盡，請稍後再試！")
                    st.stop()

        st.session_state.input_value = ""

        if st.button("👉 下一題"):
            st.session_state.submitted = False
            st.session_state.current_index += 1
            st.rerun()

# 測驗結束畫面
else:
    st.write(f"🎉 測試結束！共回答 {len(st.session_state.words)} 題")

    if st.session_state.mistakes and test_type != "單字造句":
        st.write("❌ 你答錯的單字：")
        for word, meaning, example in st.session_state.mistakes:
            st.write(f"**{word}** - {meaning}")
            st.write(f"例句：{example}")
            st.write("---")

    if st.button("🔄 重新開始"):
        st.session_state.words = get_unique_words(num_questions)
        st.session_state.current_index = 0
        st.session_state.score = 0
        st.session_state.mistakes = []
        st.session_state.submitted = False
        st.session_state.input_value = ""
        st.rerun()
