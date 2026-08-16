# 銘柄ウォッチ（stock-dashboard）

気になる日本株・米株の6ヶ月チャートと指標を、スマホから1画面で確認するためのダッシュボード。

GitHub Actions が定時に株価を取得して `data.json` を更新し、GitHub Pages が `index.html` を配信する。
**取得（Python）と表示（HTML）を分離しているため、ブラウザのCORS制限に引っかからない。**

---

## 構成

```
stock-dashboard/
├── index.html                      表示（依存ライブラリなし・単体で動作）
├── tickers.json                    監視銘柄リスト ← ここを編集して銘柄を増減
├── data.json                       Actions が自動生成（手で触らない）
├── requirements.txt
├── scripts/
│   ├── fetch_data.py               yfinance で取得 → data.json 出力
│   └── make_sample.py              オフライン表示確認用のダミーデータ生成
└── .github/workflows/update-data.yml
```

---

## セットアップ（5ステップ）

1. GitHub でリポジトリを作成（**Public** 推奨。Private でも Pages は使えるが有料プランが必要）
2. このフォルダ一式をアップロード
3. **Settings → Pages** → Source を `Deploy from a branch` / Branch を `main` `/ (root)` にして Save
4. **Settings → Actions → General** → Workflow permissions を `Read and write permissions` に変更して Save
   （これを忘れると `data.json` の push が権限エラーで失敗する）
5. **Actions タブ → Update stock data → Run workflow** で初回を手動実行

完了後 `https://<ユーザー名>.github.io/<リポジトリ名>/` をスマホで開く。
iPhone なら Safari の共有 → **ホーム画面に追加** でアプリのように起動できる。

---

## 銘柄の追加・削除

`tickers.json` を編集するだけ。スマホの GitHub アプリからでも直接編集できる。

```json
{ "symbol": "6758.T", "name": "ソニーグループ", "group": "JP" }
```

- 日本株: 4桁コード + `.T` （例 `7203.T`）
- 米国株: ティッカーそのまま（例 `AAPL`）
- `group` はタブの区分。`JP` / `US` 以外の文字列を入れると新しいタブが増える
- `exchange` は Google Finance のリンク生成用。省略時は日本株 `TYO` / 米国株 `NASDAQ`。
  **NYSE上場銘柄（KO, JNJ, XOM など）は `"exchange": "NYSE"` を明示する**こと。省略するとGoogleのリンクが404になる

`indices` に `"pin": true` を付けた指数（既定はドル円）は、上部バーを横スクロールしても左端に固定表示される。

保存すると次回のスケジュール実行で反映される。すぐ反映したいときは Actions から手動実行。

---

## 更新タイミング

| cron (UTC) | 日本時間 | 目的 |
|---|---|---|
| `30 7 * * 1-5` | 平日 16:30 | 日本市場の大引け後 |
| `0 22 * * 1-5` | 平日 翌07:00 | 米国市場の引け後 |

GitHub の schedule は混雑時に数分〜十数分ずれる（公式仕様）。

---

## データソースと制約

| 項目 | 出所 | 備考 |
|---|---|---|
| 株価・6ヶ月日足・前日比・5日騰落 | yfinance | 十分な精度 |
| PER / PBR / 配当利回り | yfinance `info` | 日本株は欠損することがある（`—` 表示） |
| 決算（売上高・純利益・増収増益期数） | yfinance `income_stmt` | **通期実績のみ** |
| 通期予想に対する進捗率 | — | **未対応**（下記参照） |
| 判断スコア | 自前算出 | みんかぶの投資判断は転載不可のため代替 |

### 株探・みんかぶを直接読みに行かない理由

株探は公式ヘルプで、プログラムによるデータの機械的取得（スクレイピング）を明確に禁止している。
Yahoo!ファイナンス日本版も同様。したがって本ツールは両サイトを**閲覧リンクとしてのみ**扱い、
数値はライセンス上問題のない yfinance から取得している。

### 進捗率を出したくなったら

通期会社予想は無料の一般APIでは取れない。実装するなら次の2択。

- **J-Quants API**（JPX公式）: 無料プランは12週間遅延のため当日値には使えない。Lightプラン（月額1,650円〜）で当日データが取得可能
- **EDINET API**（金融庁・無料）: XBRL から予想値を自前で抽出。実装コストは高いが費用ゼロ

---

## ローカルでの確認

`index.html` をダブルクリックで開くと、ブラウザの制限で `data.json` を読めない。必ずサーバ経由で開く。

```bash
python scripts/make_sample.py   # ダミーデータを生成（初回の見た目確認用）
python -m http.server 8000
# → http://localhost:8000
```

実データで試すとき:

```bash
pip install -r requirements.txt
python scripts/fetch_data.py
```

---

## 銘柄リンクについて

各カードから3サイトの銘柄ページへ飛べる。

| リンク | 内容 |
|---|---|
| 株探 | 決算・材料ニュース中心 |
| Yahoo | Yahoo!ファイナンス。気配・出来高・掲示板 |
| Google | Google Finance。米株の比較がしやすい |

### 板（気配）は見られない

**無料・ログイン不要でフル板を表示できるサイトは存在しない。**
Yahoo!ファイナンスでもリアルタイム株価と板気配は有料のVIP倶楽部限定。
板を出しているのは松井証券の株価ボード、大和証券、SMBC日興のBRiSKなど、
いずれも口座＋ログインが必要な証券会社ツールに限られる。

したがって本ツールのリンクは「銘柄ページへ最短で飛ぶ導線」と割り切り、
板が必要な場面では証券会社アプリを開く運用とする。

### Google Finance をデータ源にしなかった理由

- Google Finance API は 2011年に廃止済み。公式に残るのは Googleスプレッドシートの `GOOGLEFINANCE` 関数のみで、スプレッドシート外からは呼べない
- 東証で最大20分の遅延がある
- PER / PBR / 決算などの指標が取れない

以上から、リンク先としては採用し、データ源は yfinance のままとした。

---

## 判断スコアについて

外部サイトの投資判断は転載できないため、公開データから機械的に0〜6点を算出している。

| 加点条件 | |
|---|---|
| 株価 > 25日移動平均 | +1 |
| 25日移動平均 > 75日移動平均 | +1 |
| 直近5営業日の合計騰落がプラス | +1 |
| PER < 15 | +1 |
| PBR < 1.0 | +1 |
| 直近期が増収かつ増益 | +1 |

条件は `scripts/fetch_data.py` の `compute_score()` に集約してあるので、自分の見方に合わせて自由に変更できる。

**これは投資助言ではない。** 売買の判断は自己責任で。

---

## 文字コードについて

HTML / JSON / Python は **UTF-8** で保存している。JSON仕様と GitHub の要件上、
Shift_JIS では日本語の銘柄名が文字化けして動作しないため、このプロジェクトのみ例外扱いとしている。
