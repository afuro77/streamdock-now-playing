# Stream Dock Now Playing

[English README（正文）](README.md)

Windows GSMTCとStream Dock互換デバイスを利用するNow Playing／メディアコントローラーです。
AJAZZ AKP03J（ホスト表記AKP03E_3220）で開発しています。

**全機能のソースを含む開発中のプレビューです。** 完成版インストーラーではありません。
ソースのMITライセンスと外部サービス・画像・ロゴの利用権は別です。

- Spotify／Media：GSMTC、ジャケット、再生・音量。任意のPKCE連携でQueue、Liked Songs、
  プレイリスト、曲詳細、Connect等。
- Desktop：時計・日付、天気、洗濯の目安、汎用アプリ起動、マスター音量。
- YouTube：ブラウザ制御、一覧、LCD動画転送、コマ数設定・受信実測。**非公式実験機能**です。

YouTubeとSpotify埋め込みページの解析は、規約適合を確認できていません。注記や自己責任の
表明で許諾されるわけではなく、ソース公開もサービス利用の許可を意味しません。
初期設定ではSpotify API／YouTube連携を無効にしています。
[外部サービスの条件](docs/SERVICES.md)を確認してください。

下段アプリ枠はAPP 1〜3の未設定状態が標準です。表示名・起動先・画像を設定できます。
Steam／LINE／Codex等は設定例／利用者の選択であり、本体やロゴは同梱しません。
[アプリ起動設定](docs/APP_LAUNCHERS.md)を参照してください。

[導入・削除](docs/INSTALL.md)、[移行と復旧](docs/MIGRATION.md)、
[既知の制約](docs/KNOWN_LIMITATIONS.md)、[個人情報の扱い](PRIVACY.md)、
[公開前確認](docs/PUBLICATION_REVIEW.md)を用意しています。
対応表・テスト手順・ライセンスの詳細は英語READMEを正文とします。

公開プラグインの名前空間は `org.streamdock.nowplaying.public`。
既存の安定版v1やDEVを置換せず、別プロファイルで試してください。
