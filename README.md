# IQ Option Automated Trading Bot (v1.0 Pro)

ระบบเทรดอัตโนมัติสำหรับ IQ Option รองรับการเทรด Binary Options แท่งเทียน 1 นาที (M1) และ 5 นาที (M5) พร้อมกลยุทธ์ความแม่นยำสูง (Multi-Timeframe Trend-Pullback), การบริหารเงินทุน Martingale 5 สเต็ป, ระบบสแกนคู่เงิน Payout $\ge$ 80% อัตโนมัติ, แจ้งเตือนผ่าน Telegram, และ Web Dashboard ควบคุมแบบ Real-time

---

## 🌟 ฟีเจอร์เด่น (Key Features)

1. **กลยุทธ์ Multi-Timeframe Trend + Pullback (High Win Rate)**:
   - **M5 Trend Context**: กรองแนวโน้มใหญ่ด้วย **EMA 50** (ราคาอยู่เหนือ EMA เทรดเฉพาะ **CALL**, อยู่ใต้ EMA เทรดเฉพาะ **PUT** ไม่สวนเทรนด์)
   - **M1 Entry Pullback**: รอจังหวะราคาย่อตัวแตะขอบ **Bollinger Bands (20, 2)** ร่วมกับสัญญาณ **RSI (14)** Overbought/Oversold เพื่อเข้าสัญญาที่มีแต้มต่อสูง
2. **การบริหารเงิน Martingale 5 สเต็ป พร้อม Safety Cut-Loss**:
   - ไม้ 1: **$1.00**
   - ไม้ 2: **$2.20**
   - ไม้ 3: **$5.00**
   - ไม้ 4: **$11.00**
   - ไม้ 5: **$25.00**
   - ชนะไม้ใดก็ตาม $\rightarrow$ รีเซ็ตกลับไปไม้ 1 ทันที
   - **Safety Cut-Loss**: หากแพ้ครบ 5 ไม้ จะตัดขาดทุนทันทีและรีเซ็ตกลับไม้ 1 (ไม่ทบต่อไม้ที่ 6 ป้องกันพอร์ตแตก)
   - **Daily Stop-Loss & Take-Profit**: บอทจะหยุดทำงานทันทีเมื่อขาดทุนหรือได้กำไรถึงเป้าหมายประจำวันที่ตั้งไว้
3. **ระบบสแกน Payout $\ge$ 80% อัตโนมัติ (Asset Scanner)**:
   - สแกนหาคู่เงินที่เปิดให้เทรดทั้งหมด (ทั้งตลาดปกติและ OTC วันหยุด)
   - เลือกเทรดเฉพาะคู่เงินที่ให้อัตราผลตอบแทน Payout สูงกว่า 80% ขึ้นไป เพื่อความได้เปรียบทางสถิติ
4. **ระบบแจ้งเตือนผ่าน Telegram (Telegram Alerts)**:
   - แจ้งเตือนเมื่อบอทเปิด/ปิดออเดอร์ พร้อมบอกคู่เงิน, ทิศทาง (CALL/PUT), จำนวนเงิน, ไม้ที่ และเหตุผลสัญญาณ
   - แจ้งเตือนผลลัพธ์ WIN 🟢 หรือ LOSS 🔴 ทันที พร้อมยอดเงินคงเหลือ และเตือนเมื่อแตะ Stop Loss / Take Profit
5. **Modern Real-time Web Dashboard**:
   - หน้าจอควบคุม Dark Theme พัฒนาด้วย FastAPI + WebSocket
   - แสดงผล Balance, Win Rate, ประวัติการเทรด, รายชื่อคู่เงิน Payout สูง, และ Terminal Log แบบสดๆ
   - ปุ่ม Start / Stop บอท และฟอร์มปรับเปลี่ยนพารามิเตอร์ได้โดยไม่ต้องรีสตาร์ต

---

## 📂 โครงสร้างโฟลเดอร์โปรเจกต์

```
d:\WebAppGemeni\BotIqoption\
├── app/
│   ├── config.py                 # ตัวแปรระบบและการตั้งค่า
│   ├── core/
│   │   ├── client.py             # เชื่อมต่อ IQ Option และ Auto-Reconnect
│   │   ├── scanner.py            # สแกนคู่เงิน Payout >= 80%
│   │   ├── data_feed.py          # ดึงแท่งเทียน M5 และ M1
│   │   ├── executor.py           # ส่งออเดอร์และเช็คผล Win/Loss
│   │   └── bot_controller.py     # ตัวควบคุมวงรอบการทำงานของบอท
│   ├── strategies/
│   │   ├── base.py               # โครงสร้างกลยุทธ์
│   │   └── trend_pullback.py     # กลยุทธ์ EMA 50 + BB(20,2) + RSI(14)
│   ├── risk/
│   │   └── money_manager.py      # คำนวณ Martingale 5 ไม้ และ Stop-Loss
│   ├── utils/
│   │   ├── logger.py             # บันทึกกิจกรรมลง Log และ Web UI
│   │   └── telegram_bot.py       # แจ้งเตือนเข้า Telegram
│   └── web/
│       ├── server.py             # FastAPI REST & WebSocket Server
│       └── templates/
│           └── index.html        # หน้าจอ Web Dashboard
├── .env                          # ไฟล์ตั้งค่าส่วนตัว (รหัส IQ Option, Telegram Token)
├── .env.example                  # ตัวอย่างการตั้งค่า
├── requirements.txt              # รายการแพ็กเกจ Python
├── run_web.py                    # คำสั่งเปิด Web Dashboard (พอร์ต 8000)
├── run_bot.py                    # คำสั่งเริ่มบอทแบบ Console (CLI)
├── test_system.py                # ชุดทดสอบ Unit Test ระบบหลัก
└── test_web_server.py            # ชุดทดสอบ Web Dashboard API
```

---

## 🚀 วิธีติดตั้งและเริ่มต้นใช้งาน (Quickstart)

### 1. เข้าสู่โฟลเดอร์โปรเจกต์และเปิดใช้งาน Virtual Environment
เปิด PowerShell ที่โฟลเดอร์ `d:\WebAppGemeni\BotIqoption`:
```powershell
.\venv\Scripts\Activate.ps1
```

*(หากยังไม่ได้ติดตั้งแพ็กเกจ ให้รัน `pip install -r requirements.txt`)*

---

### 2. ตั้งค่าไฟล์ `.env`
เปิดไฟล์ `.env` เพื่อใส่ข้อมูลของคุณ:
```ini
# บัญชี IQ Option
IQ_EMAIL=your_email@example.com
IQ_PASSWORD=your_password

# โหมดบัญชี: PRACTICE (แนะนำสำหรับทดสอบ) หรือ REAL
ACCOUNT_MODE=PRACTICE

# การบริหารเงินทุน Martingale 5 ไม้
BASE_BET=1.0
MARTINGALE_STEPS=5
CUSTOM_STEPS=1.0,2.2,5.0,11.0,25.0

# ขีดจำกัดความเสี่ยงรายวัน
DAILY_STOP_LOSS=50.0
DAILY_TAKE_PROFIT=30.0

# การแจ้งเตือน Telegram
# 1. ขอ Token จากบอท @BotFather ใน Telegram
# 2. ขอ Chat ID ของคุณจากบอท @userinfobot ใน Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=true
```

> **หมายเหตุ**: สามารถกรอกหรือแก้ไขข้อมูลผ่านทางหน้าจอ Web Dashboard ได้เช่นกัน!

---

### 3. รันโปรแกรม Web Dashboard (แนะนำ)
รันคำสั่ง:
```powershell
.\venv\Scripts\python run_web.py
```
เปิดเบราว์เซอร์ไปที่: **`http://localhost:8000`**
- หน้าเว็บจะแสดงข้อมูลยอดเงิน, สถานะบอท, สัญญาณอินดิเคเตอร์สด, ประวัติออเดอร์ และรายการคู่เงิน
- กดปุ่ม **START BOT** เพื่อเริ่มการทำงานได้ทันที

---

### 4. รันโปรแกรมแบบ Console (CLI Mode)
หากต้องการรันบอทในโหมดเบื้องหลังโดยไม่เปิดหน้าเว็บ:
```powershell
.\venv\Scripts\python run_bot.py
```

---

## 🧪 การทดสอบระบบ (Automated Tests)
รันคำสั่งเพื่อทดสอบความถูกต้องของตรรกะ Martingale, อินดิเคเตอร์, Scanner และ Web API:
```powershell
.\venv\Scripts\python -m unittest discover -s . -p "test_*.py"
```

---

## 🛡️ คำเตือนความปลอดภัย (Safety & Risk Guidelines)
1. **ทดสอบบนบัญชีฝึกหัด (PRACTICE) เสมอ**: ระบบถูกตั้งค่าเริ่มต้นเป็นโหมด Demo เพื่อให้มั่นใจในความถูกต้องของสูตรเทรดก่อนใช้เงินจริง
2. **ไม่ควรปิดระบบ Stop Loss**: ตลาดการเงินมีความผันผวนสูง การตั้งค่าเพดานขาดทุนรายวันจะช่วยป้องกันความเสียหายร้ายแรงต่อพอร์ต
"# BotIqoption" 
