import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from openai import OpenAI
import plotly.express as px

# ==========================================
# 1. 設定區 (請換上新的 Key!)
# ==========================================

# ⚠️ 請填入你 "新申請" 的 OpenAI API Key
API_KEY = "請填入你的Key" 

# 資料庫連線設定
DB_USER = "ss469"
DB_PASS = "ir9481"
DB_HOST = "203.64.37.61"
DB_NAME = "IRstdb"

# 連線字串 (加上 TrustServerCertificate=yes 以通過 SSL 驗證)
CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=API_KEY)

# ==========================================
# 2. 核心功能函式
# ==========================================

def get_sql_from_ai(user_question):
    """
    將使用者的中文問題 -> 轉換成 SQL Server (T-SQL) 語法
    """
    # 優化後的 Schema 描述
    # 我移除了重複的 DepartmentName，並讓 AI 知道這是「在學人數」資料
    schema_info = """
    資料表名稱: CU_ST_1_1 (各系所學制在學學生人數統計表)
    欄位:
    - fyy (學年, varchar(10)) -> 例如 '114' 或 '113'
    - SchoolStatCode (學校代碼, char(10)) 
    - DepartmentName (系所名稱, varchar(100)) -> 例如 '資訊工程系'
    - ProgramClass (學制班別, varchar(100)) -> 例如 '日間部四技', '碩士班'
    - TotalStudents (在學學生數小計, int)
    - MaleStudents (在學學生數男, int)
    - FemaleStudents (在學學生數女, int)
    """

    system_prompt = f"""
    你是一個 SQL Server (T-SQL) 專家。請根據以下 Schema 將使用者的問題轉換成 SQL 查詢。
    Schema: {schema_info}
    
    規則：
    1. 只回傳 SQL 代碼，不要包含 markdown (如 ```sql)。
    2. 使用者若問「多少人」、「統計」，請使用 SUM(TotalStudents) 並搭配 GROUP BY。
    3. 針對字串欄位比較，請務必加上 N 前綴 (例如: DepartmentName = N'資訊工程系')。
    4. 欄位 fyy 是 varchar，查詢時請用字串格式 (例如 fyy = '114')。
    5. 不要自己發明欄位，只能用 Schema 裡有的。
    """

    response = client.chat.completions.create(
        model="gpt-4o", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ],
        temperature=0
    )
    
    sql = response.choices[0].message.content.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

def execute_query(sql_query):
    """
    連線到 SQL Server 執行指令並回傳 DataFrame
    """
    try:
        # 建立連線引擎
        engine = create_engine(CONN_STR)
        with engine.connect() as conn:
            # 執行查詢
            df = pd.read_sql(text(sql_query), conn)
            return df, None
    except Exception as e:
        return None, str(e)

# ==========================================
# 3. 網站介面 (Streamlit)
# ==========================================

st.set_page_config(page_title="校務數據 AI 助理", layout="wide")

st.title("🎓 校務數據 AI 助理 (CU_ST_1_1)")
st.markdown("目前資料庫連接至：**學生人數統計表**")
st.info("💡 提示：您可以問「113學年各系所的學生人數？」或「113學年資訊工程系的男女比例？」")

# 使用者輸入框
user_query = st.text_input("輸入查詢問題：", "113學年各系所學生人數統計")

if st.button("開始分析"):
    with st.spinner("AI 正在思考 SQL 語法..."):
        # Step 1: 取得 SQL
        generated_sql = get_sql_from_ai(user_query)
        
        with st.expander("查看 AI 生成的 SQL 語法"):
            st.code(generated_sql, language="sql")

        # Step 2: 執行 SQL
        df, error = execute_query(generated_sql)

        if error:
            st.error(f"資料庫查詢失敗：{error}")
            st.warning("請確認您是否連得上校內網路 (203.64.37.61)？或是資料庫密碼是否正確？")
        elif df.empty:
            st.warning("查詢成功，但沒有找到符合的資料 (可能是年份不對或系名打錯)。")
        else:
            st.success(f"查詢成功！共找到 {len(df)} 筆資料")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("📋 詳細數據")
                st.dataframe(df)

            with col2:
                st.subheader("📊 視覺化圖表")
                
                # 自動繪圖邏輯
                num_cols = df.select_dtypes(include=['number']).columns
                cat_cols = df.select_dtypes(include=['object']).columns

                if len(num_cols) > 0 and len(cat_cols) > 0:
                    x_axis = cat_cols[0] # 取第一個文字欄位 (如系所)
                    y_axis = num_cols[0] # 取第一個數字欄位 (如人數)
                    
                    tab1, tab2 = st.tabs(["長條圖", "圓餅圖"])
                    
                    with tab1:
                        fig_bar = px.bar(df, x=x_axis, y=y_axis, title=f"{x_axis} vs {y_axis}", text_auto=True)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    with tab2:
                        fig_pie = px.pie(df, names=x_axis, values=y_axis, title=f"{x_axis} 佔比")
                        st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("資料格式不適合自動繪圖，請參考左側表格。")