# AKP03J：現状・技術的な余地・改善案

調査日：2026-10-19。**本書は提案であり、機能の実装・割当変更は行っていません。**

## 保存状態と今後の前提

- 実機の安定版：`ajazz-media` v1.0.0。Spotify Mediaプロファイルを維持。
- 開発候補：`streamdock-now-playing`。責務分離済みソースと13件のテストを作成途中のまま保持。実機には未導入。
- 公開準備・公開前監査は中断。公開可能との最終判定は出していない。GitHub公開・pushなし。
- v1のplugin.py、media.py、test_plugin.py、プラグインmanifestはv1バックアップとのSHA-256一致を確認。
- 今後の目的は、個人の日常利用の改善。OAuth・Like/Saveは今回の改善候補から除外。
- 今回の実機調査は情報の読み取りのみ。再生、音量、Shuffle等の変更コマンドは送信していない。

## 1. 現在の割当と未使用操作

座標はホストの `(column,row)`。物理配置の通常の行列とは一致しない箇所がある。

| 部品 | 座標 | 表示／通常操作 | 押下 | 未使用の操作判定 |
|---|---|---|---|---|
| LCD左上 | 0,0 | ジャケット左上、tile 0 | Play/Pause | 解放、長押し、ダブルクリック |
| LCD上中央 | 1,0 | ジャケット上中央、tile 1 | Play/Pause | 同上 |
| LCD右上 | 2,0 | ジャケット右上、tile 2 | Play/Pause | 同上 |
| LCD左下 | 0,1 | ジャケット左下、tile 3 | Play/Pause | 同上 |
| LCD下中央 | 1,1 | ジャケット下中央、tile 4 | Play/Pause | 同上 |
| LCD右下 | 2,1 | ジャケット右下、tile 5 | Play/Pause | 同上 |
| 大ノブ | 3,0 | 回転：SpotifyのWindowsアプリ音量、1 tick＝2ポイント | Play/Pause | 解放、長押し、押し込み回転の区別 |
| 左小ノブ | 3,1 | 反時計回り：前曲、時計回り：次曲 | **未割当** | 解放、長押し、押し込み回転の区別 |
| 右小ノブ | 4,1 | 回転：1 tick＝5秒シーク | Shuffle切替 | 解放、長押し、押し込み回転の区別 |
| 下部左ボタン | 5,0 | ジャケット／曲名・アーティスト表示の切替 | 左記 | 解放、長押し、ダブルクリック |
| 下部中央ボタン | 5,1 | Spotify固定／Windows現在のメディアセッション切替 | 左記 | 同上 |
| 下部右ボタン | 5,2 | ジャケット表示へリセット、一時表示解除 | 左記 | 同上 |

LCDの6押下は同じ機能で、表示中のジャケットはどこを押しても再生／一時停止できる。別々の機能に割り当てる余地はあるが、現状は操作の一貫性を優先している。

補足：

- 操作結果を約2.5秒間、6枚すべてに同じ小さなカードとして表示し、その後元の表示モードに戻る。
- 下部左で情報モードを選んだ場合、無操作でも情報モードのまま。常にジャケットに戻る仕様ではない。
- 左小ノブはticksの符号を使い、1イベントにつき前曲／次曲を1回送る。ticksの絶対値を曲数にはしていない。
- 押し込み中の回転は現行では通常回転と同じ扱い。押した瞬間のPlay/Pause／Shuffleも先に発生する。
- 下部ボタンの割当はコード・プロファイルで確認。以前の実機確認には下部3ボタンの個別検証を含めていない。
- ノブ用に送るアイコン画像が、非LCDのノブ自体に表示されるとは限らない。6 LCD以外に追加画面がある前提では設計しない。

## 2. Stream Dock SDKの入力・通知

公式Received Events仕様で列挙されるイベントを以下に整理した。**SDK仕様上の存在とAKP03Jでの実測は別**である。

### 操作入力：5種類

| イベント | 内容 | 現行v1 |
|---|---|---|
| keyDown | LCDキー／物理ボタンを押す | 使用 |
| keyUp | キー／ボタンを離す | 未処理 |
| dialDown | ノブを押す | 使用。左小ノブは処理を終了して何もしない |
| dialUp | ノブを離す | 未処理 |
| dialRotate | ノブを回す | ticksを使用。pressedは未使用 |

`dialRotate`の仕様には、符号付きticksと押し込み中を示すpressedがある。pressedの実機での出方は未検証。
長押し・短押し・ダブルクリック・連続回転の速度は、専用イベントとしては定義されていない。押下／解放の時間や回転イベントの間隔から、開発版で判定できる候補である。
複数キーの同時押しや、押し込み回転時のイベント順序は実機検証が必要。
タッチバーのtouchTapやスワイプをAKP03Jの入力として利用できる証拠はなく、設計の前提にしない。

### 設定・ライフサイクル通知：12種類

| 分類 | イベント | 用途 |
|---|---|---|
| 設定 | didReceiveSettings / didReceiveGlobalSettings | キー別／全体設定の反映 |
| アクションの有効化 | willAppear / willDisappear | プロファイル切替、表示先の生成・解放 |
| タイトル | titleParametersDidChange | 文字の表示設定変更 |
| デバイス | deviceDidConnect / deviceDidDisconnect | 接続状態の管理 |
| 監視アプリ | applicationDidLaunch / applicationDidTerminate | manifestで指定したアプリの起動・終了 |
| Windows復帰 | systemDidWakeUp | スリープ復帰。通知直後のデバイス準備完了は保証されない |
| 設定UI | propertyInspectorDidAppear / propertyInspectorDidDisappear | プロパティ画面の生成・破棄 |

加えて、設定UIからプラグインへの`sendToPlugin`がある。逆方向の`sendToPropertyInspector`は設定UIが受信する通信イベント。
現行v1が処理する通知はwillAppear、willDisappear、didReceiveSettings。残りは復旧や設定UI改善の余地。

出典：[公式Received Events](https://sdk.key123.vip/en/guide/events-received.html)。

## 3. LCDで実現可能な表示

| 表示 | 方法と現状 | 留意点 |
|---|---|---|
| テキスト | setTitle、または画像に描画。現行はPillowで日本語を画像化 | 現行manifestはホストのタイトル表示を無効化。setTitleだけ追加しても表示されない可能性 |
| 曲名・歌手・アルバム | 取得データを画像化 | 曲名・歌手は既存情報モードで表示。アルバム名は取得済みだが未表示 |
| スクロール文字 | 文字位置を少しずつ変えてsetImage | 描画自体は可能。読みやすさ・更新負荷は未検証 |
| 進捗・残り時間 | position／durationからバーと数字を描く | 情報取得は既存。なめらかな補間にはLastUpdatedTime等の扱いを追加する必要 |
| 再生／停止・Shuffle・Repeat状態 | アイコン・色・ラベル、setStateで切替 | 再生・Shuffleは取得済み。Repeatは追加取得が必要 |
| 音量・消音状態 | Windows Audio Sessionの値をバー／数字で表示 | 現行は音量を操作したときの結果だけを表示 |
| 6枚を1画面として使う | 1枚の仮想キャンバスを分割して6回送信 | 6画面同時更新の原子的保証はなく、多少の更新差があり得る |
| 一部分だけOverlay | ジャケットの下帯だけ暗くし、数字や文字を重ねる | 6面全面を同じカードで置換する現状から改善できる |
| 接続・失敗表示 | 自作画像、showAlert／showOk | 正常・未起動・非対応・失敗を区別できる |
| SVG／GIF | SDKのsetImage仕様はSVG、GIFも記載 | AKP03JでのGIFアニメ再生・速度は未検証。SVG対応はSVGアニメ対応の保証ではない |
| アニメーション／メーター | 連続する静止画として更新 | 更新可能fps、帯域、CPU、ちらつきを実機で測る必要。動画プレーヤー相当の機能は保証しない |

現在は各タイル128×128の画像を送る。これは実装の送信サイズであり、ここではパネルのネイティブ解像度を保証しない。
ジャケットは3:2に中央クロップしているので、正方形の上下が切れる。全体表示は余白を入れるcontain方式で可能。LCD間の隙間補正も未実装。

出典：[公式Events Sent](https://sdk.key123.vip/en/guide/events-sent.html)。

## 4. GSMTCで取得・操作できる内容

### 取得情報

| 区分 | v1で取得しているもの | APIにはあるがv1未使用のもの |
|---|---|---|
| メディア情報 | 曲名、歌手、アルバム名、サムネイル | アルバムアーティスト、曲番号、曲数、ジャンル、サブタイトル、メディア種別 |
| 再生状態 | 再生中か、Shuffle状態、各操作の対応フラグ | 詳細な停止／一時停止等の区別、Repeat状態、再生速度、再生種別 |
| タイムライン | 現在位置、終端時刻をdurationとして保持 | 開始時刻、シーク可能範囲、最終更新時刻のUI利用 |
| セッション | 発信元アプリID、セッション列挙、Windowsの現在セッション | アプリ選択リストのLCD表示 |
| 変更通知 | v1は0.5秒ポーリング | メディア情報・再生状態・タイムライン・セッション一覧・現在セッションの変更イベント |

### このPCでの読み取り結果

SpotifyとChromeのセッションを検出。Spotifyでは曲名、歌手、アルバム、アルバムアーティスト、曲番号、サムネイル、現在位置と長さを取得できた。曲数は0、ジャンルは空、サブタイトルも空だった。APIに項目があっても、アプリが値を埋めるとは限らない。

Repeatやメディア種別の列挙型を現行Python環境で読むと、対応するWinRT型投影が不足してAttributeErrorとなった。これらをUIに使う場合、開発版で追加の`winrt-Windows.Media`等の依存関係確認が必要。安定版の依存関係は変更していない。

### 操作

| 操作 | 現行／現在のSpotify |
|---|---|
| Play/Pause、前曲／次曲 | 実装・実機確認済み |
| 指定位置へのシーク | API対応。現行UIは相対5秒ずつ |
| Shuffle | 実装・実機確認済み |
| Playのみ／Pauseのみ | APIに個別操作あり。v1はトグルのみ |
| Stop | 対応フラグtrue。コマンド未実装・動作未検証 |
| Repeat Off／全体／1曲 | 対応フラグtrue。依存型・コマンド・動作は未検証 |
| FastForward／Rewind | 対応フラグtrue。相対シークとは別操作。動作未検証 |
| 再生速度変更 | APIはあるが現在のSpotify対応フラグfalse |
| Record、チャンネル上下 | APIにはあるが現在のSpotify対応フラグfalse。音楽操作での優先度は低い |

対応フラグtrueは、実コマンドが確実に成功する保証ではない。成功結果と操作後の状態で確認が必要。

GSMTC単独で取得できないもの：プレイリスト一覧、再生キュー全体、次曲の詳細、Like/Save状態、歌詞、音質・ビットレート、波形・FFT、プレーヤー固有の検索・レコメンド。
GSMTCには音量APIもなく、音量は別のWindows Audio Sessionから操作している。

出典：[Media Properties](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionmediaproperties?view=winrt-26100)、[Playback Info](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionplaybackinfo?view=winrt-26100)、[Timeline](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessiontimelineproperties?view=winrt-26100)、[Session操作](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssession?view=winrt-26100)。

## 5. Windows側から追加できる候補

| 候補 | 取得・操作方法 | 今回の評価 |
|---|---|---|
| アプリ別音量の現在値・消音 | Core AudioのISimpleAudioVolume | 実装済み音量処理の延長。消音フラグを使えば元の音量を維持できる |
| 音量プリセット／ゆっくり戻す | 音量API＋タイマー | 作業用の音量へ戻す、急な音量変化を避ける。任意機能として有用 |
| 別アプリの音量 | Audio Session列挙とプロセス対応付け | 実現可能。ブラウザーはタブ単位と音声セッションが一致するとは限らない |
| Windows全体の音量・消音 | IAudioEndpointVolume | アプリ音量とは別。会議音声も変わるので別モードで明示する必要 |
| 音が実際に出ているか／ピーク | IAudioMeterInformation | 再生中なのに無音、消音中などの診断。セッション／デバイス単位の対応確認が必要 |
| 出力デバイス名・接続状態 | MMDevice API | ヘッドホン等の接続確認に有用 |
| 出力先切替 | 既存Stream DockプラグインやWindows連携を検討 | デバイス列挙と、既定出力変更は別。安定した切替方式の検証が必要で、Core Audio列挙APIだけで完結すると断定しない |
| スリープタイマー | Windows上のローカルタイマー＋Pause | 認証不要。全体シャットダウンは不要 |
| アプリ起動 | 起動経路・アプリ登録情報 | 未起動から再生環境を準備。起動だけで自動再生できるとは限らない |
| ローカル再生履歴・曲内ブックマーク | 取得した曲情報と位置をローカル保存 | 同じ曲を特定できる範囲で表示可能。履歴から曲を直接呼び出せる保証はない |
| 波形・スペクトラム | WASAPI loopback等で音声を取得し解析 | 別の音声取得処理が必要。仕事中の実用性より負荷・見た目寄りなので低優先 |
| アプリ固有ショートカット／UI操作 | 対象アプリの機能に依存 | フォーカス・更新で壊れやすい。日常の主要操作にはGSMTCを優先 |

出典：[Session Volume](https://learn.microsoft.com/en-us/windows/win32/coreaudio/session-volume-controls)、[Endpoint Volume](https://learn.microsoft.com/en-us/windows/win32/api/endpointvolume/nn-endpointvolume-iaudioendpointvolume)、[Audio Devices](https://learn.microsoft.com/en-us/windows/win32/coreaudio/enumerating-audio-devices)、[Loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)。

## 6. すでにある処理・情報の未活用箇所

ここは「新しいバックエンド機能が必要な候補」と区別する。

| 既存のもの | 未活用のUI |
|---|---|
| snapshotのplaying | 一時停止中をひと目で分かる表示 |
| snapshotのshuffle | ON/OFFの継続的な表示、情報画面の状態表示 |
| snapshotのposition・duration | 経過／残り時間、進捗バー、シーク先の具体的な時刻 |
| snapshotのalbum | アルバム名の情報画面 |
| snapshotのsource | どのアプリを操作中かの明示 |
| snapshotのcontrols | 非対応機能を灰色表示、操作前の案内 |
| 複数セッションの列挙 | Spotify／ブラウザー等の明示的な選択画面。現行は固定／Windows任せの2択 |
| 相対seek(amount) | 5秒以外の幅、曲頭までの移動。ただし位置指定UIは未実装 |
| 任意amountのvolume | 小刻み調整、指定量増減。絶対値プリセットは追加実装が必要 |
| Pillow画像生成・6分割 | 6枚で1つの大きな操作表示、下帯Overlay、ジャケット全体表示 |

Repeat、消音、ピークメーター、出力切替、長押し判定は、技術的候補だが**現行コードに完成済みの未割当機能ではない**。

## 推奨する改善案：手の操作を保ち、画面確認の代わりを強くする

### 優先1：操作結果が読めるLCDへ

大ノブ＝音量／再生、左小ノブ＝前後曲、右小ノブ＝シーク／Shuffleは維持。
無操作時は6面ジャケットのままにする。
操作時だけ6面全体を1つの仮想キャンバスとして、音量を大きな数字、シークを移動先時刻＋バー、Shuffleを明確なON/OFFで表示する。現状の同じカード6枚から変えることで、視線を一度向けるだけで結果を読めるようにする。
最初はアニメーションを入れず、更新負荷を抑える。

### 優先2：「何が鳴っているか」を一押しで確認

下部左を「情報の一時表示」にする案。曲名・歌手・アルバム・経過／残り・操作対象アプリを分担表示し、5秒程度でジャケットへ戻る。
情報を固定したい場合だけ別の操作にする。長押しの実機検証前は、固定モードを増やさなくてもよい。

### 優先3：操作対象を迷わせない

下部中央を、利用可能なセッションを明示して切り替える操作にする案。選択時にアプリ名と曲名を表示し、選んだ対象を固定する。
ブラウザー動画を再生しただけで音楽の操作対象が意図せず変わることを避ける。対象が消えたときは別アプリへ勝手に切り替えず「対象なし」と表示する方針が合う。

### 優先4：下部右の役割を整理

現在の「ジャケットへ戻る」は、情報表示が自動復帰すれば使用頻度が下がる。その段階で「音楽だけ消音／元へ戻す」の候補にする。
最初の開発版では既存の戻る操作を維持して、表示改善の効果を先に確認する。

### 左小ノブ押下は、当面空けておく

前後曲操作中に誤って押す可能性があるため、空いていることだけを理由に割り当てない。
将来よく使うと分かった機能として「曲頭へ戻る」または「Repeat切替」が候補。Repeatは対応フラグがあっても実動作検証が必要。Like/Save・OAuthは候補に戻さない。

### 次の段階まで保留するもの

押し込み回転での細かいシーク、回転加速、長押し・ダブルクリック、出力先切替、スペクトラム表示。
特に押し込み回転を追加すると、今は押した瞬間に発生するPlay/Pause／Shuffleと衝突する。短押しを解放時に確定するなどの入力設計と、反応速度の評価が必要。

## 提案を選んだ後の開発方針

まず別の開発版で「表示だけ」の変更を試す。その後に情報の一時表示、対象セッションの明示選択を順に検証する。
安定版v1・Spotify Mediaプロファイル・バックアップは維持。開発版を実機に載せるときは、安定版と同じアクションUUIDや同じプロファイルを同時に取り合わない導入方法を事前に決める。
責務分離済みコードと13件のテストは開発ベースとして使うが、まだ実機検証済み安定版とは扱わない。

