# 紹介文の下書き（未投稿）

## AJAZZ AKP03Jを、仕事中の手元メディアコントローラーに

仕事の画面を切り替えず音楽を操作したくて、WindowsとStream Dock AJAZZ向けの
「Stream Dock Now Playing」を作っています。

6枚のLCDは、左4枚がジャケット、右側が曲情報と再生状態です。
ノブでPlay/Pauseや前曲・次曲を操作できます。Desktop Modeでは時計・天気などの
Widgetと、利用者が設定するアプリ起動Actionを配置できます。
YouTube連携も含みますが、非公式の実験機能で、利用条件の確認が必要です。

最初のジャケット表示とPlay/PauseはWindows GSMTCを使うため、Spotify Developer登録や
OAuthは不要です。QueueやConnect等のSpotify API機能には別途登録・認証と制限があります。

現在はソースプレビューで、Windows 11、Python 3.12以降、別途導入したAJAZZホストが必要です。
開発機はAKP03J（AKP03E_3220表記）。他機種への対応は未確認です。
別PCへの初回導入も、まだ実機検証を募っている段階です。

まず同じAKP03Jを持っている方に、導入・ジャケット表示・Play/Pauseを試してもらい、
機種とホスト版、困った点を教えてもらいたいです。既存プロファイルを置換せず、別枠で試します。

- [プロジェクト](https://github.com/afuro77/streamdock-now-playing)
- [認証なしで試す手順](QUICKSTART.ja.md)
- [実機確認の報告](https://github.com/afuro77/streamdock-now-playing/issues/new?template=hardware_trial.md)

実機デモは未収録です。掲載前にDEMO_PLAN.mdに沿って撮影・確認します。
投稿先のルールと宣伝可否を確認してから、所有者向けの紹介文として使ってください。
