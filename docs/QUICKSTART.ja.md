# 最初はジャケット表示と再生・停止を試す

[English](QUICKSTART.md) · [詳しい導入・削除手順](INSTALL.md)

最初はPC上のSpotifyデスクトップ版で、ジャケット表示とPlay/Pauseだけ確認します。
Play/Pauseは再生／一時停止のことです。普段のSpotifyへのログインは必要ですが、
開発者向けの登録・追加認証（Client IDやOAuth）、APIキー、Chrome拡張は不要です。
次に再生する曲の一覧（Queue）や外部スピーカー操作（Spotify Connect）、YouTubeは、
基本動作を確認した後に設定します。
公開版はソースプレビューで、別PCへの新規導入の実機確認はまだ完了していません。

使う機器はAJAZZのAKP03Jです。[公式ストアの製品写真・説明](https://store.shopping.yahoo.co.jp/ajazz/akp03j.html)
で外観を確認できます。Stream Dock AJAZZは機器を動かすためのソフト、
本プロジェクトはその中で動く追加ソフトです。

## 1. 準備

- Windows 11、AKP03J／AKP03E_3220、インストール済みのStream Dock AJAZZ。
- [Python 3.12以降](https://www.python.org/downloads/windows/)。
- GitHubの **Code → Download ZIP** でダウンロードし、常設するフォルダーへ展開。
  `pyproject.toml` があるフォルダーをPowerShellで開きます。GitやNode.jsは通常利用に不要です。
- ホスト設定をバックアップし、Stream Dockをタスクトレイから終了してください。
  ウィンドウを閉じるだけでは終了しない場合があります。補助ツールは強制終了しません。

## 2. 確認してから導入

```powershell
python tools/quickstart.py --check
python tools/quickstart.py --install
```

`python` が見つからない／Storeが開く場合は、`python` を `py -3.12` に置き換えてください。
`--check` は確認のみでファイルを書き換えません。`--install` は実行用の専用フォルダー `.venv`、
必要なPythonパッケージ、追加ソフト、プロファイル、設定保存用のフォルダー（runtime）を作成します。
プロファイルとは、ボタンの割当や画面の配置をまとめた設定です。
Stream Dock AJAZZ本体（ホストと呼びます）やドライバーは同梱しません。
Windowsの自動起動設定も変更しません。導入後もソースフォルダーは移動しないでください。

ホストの初期保存先は `%APPDATA%\HotSpot\StreamDock`、runtimeは
`%LOCALAPPDATA%\streamdock-now-playing-public` です。保存先が異なる場合は
`--host-data`／`--runtime-dir` を指定できます。
既存公開プラグイン・空でないruntime・既存 `.venv` があれば停止します。
これは初回導入用で、更新ツールではありません。既存環境では[手動手順](INSTALL.md)を使ってください。
pip失敗後に `.venv` が残る場合も、既存データを安易に削除せず手動手順で復旧します。

## 3. 実機で確認

Stream Dockを起動し **Now Playing OSS Preview** を選びます。必要ならデバイスに割り当てます。
Spotifyデスクトップ版で再生し、初回はGoogle Home等ではなくPCから音を出してください。

| 操作 | 確認すること |
|---|---|
| 曲を再生して少し待つ | 左4枚にジャケット、右側に曲情報と再生状態 |
| 大ノブ押下 | Play/Pause |
| 左小ノブ回転 | 前曲／次曲（プレーヤーの対応範囲） |
| ジャケットLCD押下 | 全面ジャケット表示。もう一度LCDを押すと戻る |

初期設定の `audio_mappings` は空なので、アプリ音量は設定後に確認します。
認証前にQueue・Playlist・Artist画像・Connectが使えないのは正常です。

## 困ったとき

- ホスト保存先が見つからない：AJAZZホストを一度起動し、保存先を確認。
- ホストが動作中：タスクトレイから終了して `--check` をやり直す。
- プロファイルが見えない：ホスト内の選択とデバイス割当を確認。旧プロファイルは残す。
- 曲が出ない：Spotifyデスクトップ版で再生し、メディアモードで確認。
- 既存データの警告：上書きせず[移行・復旧](MIGRATION.md)へ。

元へ戻すには旧プロファイルを選びます。削除はホスト終了後、ローカルの `deployment.json`
が示す公開版の保存先だけを[削除手順](INSTALL.md#uninstall)に従って取り除きます。
ホストのフォルダー全体は消さないでください。
不具合報告には機種・ホスト版・エラー文を添え、runtimeや認証ファイルは添付しないでください。
