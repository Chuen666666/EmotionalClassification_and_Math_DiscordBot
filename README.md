# Emotional Classification and Math Discord Bot
## 環境
### 基礎環境
- Python（3.9+，建議使用 3.10 ~ 3.12）
- Discord 伺服器（具管理員或擁有者的權限）
- Discord Bot（擁有 Token，並將它拉進 Discord 伺服器中）

> 不會建立 Bot 的話，可以依[這條影片](https://youtu.be/equ42VBYPrc?si=_81b7t4MDZGZwqs7)來操作

### 依賴
1. 請先把本專案 clone 下來後，建立一個 Venv
2. 使用以下指令安裝依賴

```bash
pip install -r requirements.txt
```

### 檔案修改

|原檔名|修改檔名|修改內容|
|:-:|:-:|:-:|
|`BERT_training_data.example.xlsx`|`BERT_training_data.xlsx`|將所有訓練資料和標籤依提示放入|
|`bot_token.example.env`|`bot_token.env`|將 Discord Bot 的 Token 放入|
|`server_channel.example.json`|`server_channel.json`|將 Discord 頻道 ID 依提示放入|

> 以上三個檔案皆屬於敏感資訊，請勿上傳至公開的 GitHub

> 另外，若使用 Render 來線上跑 Discord Bot，請在 Render &rarr; Service &rarr; Environment Variables 新增 `DISCORD_BOT_TOKEN = <填入你的 BOT TOKEN>`

## 訓練模型
### 生成模型檔
執行 `emo_cla.py`，待訓練完成後，可以看到終端機輸出的 `train_loss` 值是多少，它代表訓練損失，愈低表示愈準

### 調整準度
若覺得 `train_loss` 過高，可以試著：
- 重新訓練（直接重新執行 `emo_cla.py`）
- 增加或調整訓練資料（`BERT_training_data.xlsx`）
- 調整 `emo_cla.py` 中，`training_args` 變數的值：
  - `num_train_epochs`：訓練輪數（資料愈多，此值愈小，一般在 10 以內）
  - `learning_rate`：學習率（一般在 1e-5 ~ 5e-5 間，可以試著用 2e-5 或 3e-5）
  > 若修改了訓練資料，請重新執行 `emo_cla.py` 來生成新的模型檔（.pth）

## 執行 Bot 與功能介紹
### 執行 Bot
若你是在自己電腦上跑 Discord Bot，直接執行 `math_bot.py` 即可讓機器人上線

若機器人跑在 Render 環境，它會自動維持上線狀態，Render 和 UptimeRobot 的設定方式如下：

1. 將 `bert_emotion_model` 資料夾和 `bert_emotion_model.pth` 模型檔一起選取，並以 **ZIP** 加壓縮
2. 重新命名壓縮檔為 `model.zip`
3. 將壓縮檔上傳到 Google 雲端硬碟，存取權設為 **知道連結的任何人**
4. 將連結改為 Direct Link：`https://drive.google.com/file/d/你的檔案ID/view?usp=sharing` &rarr; `https://docs.google.com/uc?export=download&id=你的檔案ID`
5. 到 Render 創建一個 Web Service
6. 選擇機器人的 GitHub Repo（可先 Fork 此 Repo）
7. 回到 Render，填入以下設定
   - Runtime: `Python3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python math_bot.py`
   - Environment Variables（兩個）
     1. 填入名稱 `TOKEN` 以及具體的 Discord Bot Token 進去
     2. 填入名稱 `MODEL_URL` 以及模型 Google 雲端硬碟網址（Direct Link）
   - Advanced
   - Secret Files：`Filename` 填入 `server_channel.json`、`File Contents` 填入該 JSON 檔內容
   - Health Check Path: `/`（預設為 `/healthz`）
8.  最後點擊 `Deploy Web Service`
9.  至 UptimeRobot：創建 HTTP / website monitoring 並填入 Render 中該 Bot 的網址

### 功能簡介
- **人數統計語音頻道**
  - 總人數（`TOTAL_PPL`）
  - 真人（`REAL_PPL`）
  - 機器人（`BOT_PPL`）
- **出入提示**
  - 人員加入提示訊息（`JOIN`）
  - 人員離開提示訊息（`LEAVE`）
  - 測試加入／離開訊息（`TEST_IO`）
    - `!test_join`：測試加入訊息（須管理員或擁有者權限）
    - `!test_leave`：測試離開訊息（須管理員或擁有者權限）
- **機器人上線（更新）提示訊息**（`UPDATE`）
- **情緒判識**（`CHAT`）
  - `👍`：正向情緒
  - `👎`：負向情緒
  - 無 emoji 反應：中立情緒／無情緒／未辨識出情緒
- **數學計算斜線指令**（`COMMAND`）
  - 於頻道中輸入 `/` 即可使用，指令下方附帶說明
  - 所有使用者皆可使用

> 括號表示 `server_channel.json` 的對應頻道
> 此 Bot 未製作 `!help` 指令，使用後的輸出結果可能不如預期