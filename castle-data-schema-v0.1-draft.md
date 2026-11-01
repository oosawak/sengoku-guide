# 城館データ形式 v0.1 叩き台（2026-11-01）

ガイドサイトと戦国人生シミュレーション『奥羽一生録』で共用する城館データの設計叩き台。
本人の決定: データの正本は1つにし、ガイドとゲームの両方が同じデータを読む。コピーは作らない。

## 置き場と受け渡し（案）

- 正本: ガイド側リポの `content/places/<id>.md`（Markdown + frontmatter）
  - frontmatter = 構造化データ（共通コア＋ガイド表示項目）
  - 本文 = ガイド記事のオリジナル文章（ゲーム側は本文を使わない）
- ガイド側: build が frontmatter を `places.json`（サイト用 data.json）に変換して表示・地図に使う
- ゲーム側: 人物・出来事・合戦データは城館を `id` で参照するだけ。緯度経度はゲーム側に持たず、
  ビルド時にガイド側の生成物（places.json）を読み込んで解決する
  - 具体的な読み込み方法（生成物の取り込み方）は、ゲーム側の第2弾データ設計で確定する
  - 手でコピーした城館リストをゲーム側に置かない

## ID の規則

- 形式: `<市町村スラッグ>-<読みスラッグ>` 例: `yonezawa-yonezawa-jo` / `nagai-hakusanmori-date`
- 理由: 宮城・福島へ広げたときに同名の城館（小松城・館山など）と衝突しないようにするため
- 人物ID・イベントIDはゲーム側の既存形式と揃える
  - 人物: `date-masamune` / `naoe-kanetsugu` など（既存5人で確定済み）
  - 出来事: `kanetsugu-1601-yonezawa` など（既存イベントの id をそのまま参照）

## 共通コア（ガイド・ゲーム両方が使う）

| 項目 | 型 | 内容 |
|---|---|---|
| `id` | string | 上記の規則。場所IDとして全プロジェクト共通 |
| `name` / `yomi` | string | 城館名と読み |
| `lat` / `lng` | number | 緯度経度。正本はここだけ |
| `address` | string | 現在の所在地（市町村＋大字まで。私有地の場合はその旨も） |
| `municipality` / `prefecture` / `kuni` | string | 現在の市町村／県と、歴史的な国（出羽・陸奥など） |
| `castle_type` | string | 山城／平山城／平城／館／砦など |
| `periods` | array | 領主の変遷。`{house_id, house, from, to, role}`（本拠／居城／城代など）。1つの家に固定しない |
| `related_people` | array | `{person_id, relation, from, to, note}`。person_id はゲーム側人物ID |
| `related_events` | array | `{event_id, year, note}`。event_id はゲーム側イベントID。合戦場・移封先など |
| `related_places` | array | `{place_id, relation}`（詰城／支城／近隣など）。place_id はこのデータの id |
| `years` | object | `{founded, founded_note, active_from, active_to}`。不明は null＋note で試作値と区別 |
| `certainty` | string | confirmed／candidate／unknown。座標・年代の確からしさ |
| `sources` | array | 事実確認に使った資料（文章の転用はしない） |

家ID（house_id）の初期値: `date` 伊達家 / `mogami` 最上家 / `uesugi` 上杉家 / `nagai` 長井氏 / `gamo` 蒲生氏
（ゲーム側の人物データは現在 `house: 伊達家` の文字列形式。対応表はゲーム側第2弾で合わせる）

実装で追加した項目（2026-11-01、長井5件の作成時）:
- `clan`: 館主の氏（大町氏・安久津氏・片倉氏など）。家（house）と氏は別に持つ
- `lords`: 館主の人名リスト（文字列）。ゲーム側の人物IDがまだ無い人物用で、人物IDができたら `related_people` へ移す
- `number`: 四十八館の一覧番号（長井市は14〜18）
- `coord_precision` / `coord_note` / `coord_source`: 座標の精度（site_identified／aza_approximation）と、その根拠と出典地図
- `remains` / `designation` / `elevation_m`: 遺構・史跡指定・標高

## ガイド専用（frontmatter に同居、ゲーム側は無視する）

`title` / `date` / `category`（=市町村、既存の絞り込みを活かす）/ `summary` / `cover` / `cover_alt` / `visit_note`（私有地・立入制限・探訪上の注意）

## ゲーム専用項目を正本に混ぜない

能力値のようなゲーム固有の数値は城館データに入れない。
ゲームが将来必要になったら、ゲーム側が id 参照で自前の付加データを持つ。
逆に、年代・領主変遷・関係人物のような「事実」は共通コアに入れる。

## 例: 米沢城（値がそろっている城館での記入例）

```yaml
---
id: yonezawa-yonezawa-jo
name: 米沢城
yomi: よねざわじょう
lat: null  # 座標は確認してから記入（試作では未記入を許す）
lng: null
address: 山形県米沢市丸の内
municipality: 米沢市
prefecture: 山形県
kuni: 出羽
castle_type: 平城
periods:
  - {house_id: nagai, house: 長井氏, from: null, to: 1380, role: 居城}
  - {house_id: date, house: 伊達家, from: 1548, to: 1591, role: 本拠}
  - {house_id: gamo, house: 蒲生氏, from: 1591, to: 1598, role: 居城}
  - {house_id: uesugi, house: 上杉家, from: 1601, to: null, role: 本拠}
related_people:
  - {person_id: date-masamune, relation: 生誕地, from: 1567, to: 1591}
  - {person_id: naoe-kanetsugu, relation: 城代・本拠整備, from: 1598, to: 1619}
related_events:
  - {event_id: kanetsugu-1601-yonezawa, year: 1601, note: 上杉の米沢移封}
related_places: []
years: {founded: null, founded_note: 築城時期には諸説あり, active_from: null, active_to: null}
certainty: candidate
sources: []
# ガイド専用
title: 米沢城
date: '2026-11-01'
category: 米沢市
summary: ''
cover: ''
visit_note: ''
---
```

## 未決（本人の判断・後工程）

1. 最初の範囲（長井5館／米沢＋長井10館／48館一覧先行）― 前の提案への回答待ち
2. 座標の確定方法（天童の決め事どおり、本人が Google マップで確認する形を踏襲するか）
3. ゲーム側の取り込み方法は第2弾データ設計で確定（このファイルは参照仕様まで）

## v0.1 実装での追加（2026-11-01、試作build反映済み）
- 城館: `territory` {local_clan, approx_radius_m, basis, certainty: approximate} ― 伊達の時代の中の領主の推定範囲（円）。全体の家の色分けは時代ごとに build が生成。
- 城館: `events_timeline` [{sort_year, year_label, era: historical|modern, text, person_ids}] ― 年表の出来事。modern は軸に入れず「その後」に分離。
- 人物（content/people/）: id/name/yomi/house_id/house/clan/born/died/alias/era/`stays`[{place_id, from, to, role, certainty}] が正本。城館→人物は build が stays から生成（二重持ちしない）。`pyramid` {level, level_name, role_terms} で組織図と接続。伝記の正本がゲーム側にある人物は data_status: reference の参照ファイルに留める。
- 組織（content/organization/<house>.md）: `levels`[{level, name, description, examples: 人物ID, terms}] と `terms`[{term, yomi, description}]。人物の role_terms から用語アンカーへリンク。
- 年表の帯（時代区分）は build 側の定数 STAGES（置賜: 〜1380長井／1380〜1591伊達／1591〜1598蒲生／1598〜上杉）。「その頃いた人物」は stays の期間と出来事年から自動判定＋出来事側 person_ids の明示分を合算。

## 座標の扱い（2026-11-01 本人の方針、ゲーム側 decisions 補足と同一）
- 説明（コンテンツ）を先に作り、座標は後から入れる。座標がないことを理由にデータ作りを止めない（lat/lng は両方 null を許す。build は座標なしの城館を地図・領地・組織図から外し、一覧と記事には出す）。
- 正確な座標が取れない所は「大体この辺」の近似でよい。ただし近似であることをデータで区別する。
- 本命の埋め方は本人の現地写真: 城跡で撮った写真の EXIF GPS を座標として入れ、写真自体もガイドの素材にする。
- coord_precision の語彙: site_identified（遺跡の位置を特定）／photo_exif（本人の現地写真の位置情報由来）／aza_approximation（字・集落からの近似）／district_approximation（地区からの近似）／pending（未設定）。coord_source に根拠（地図URL・写真ファイル名と撮影日など）を必ず書く。

## number の付け替え（2026-11-01 本人の決定）
- `number` は当初の「伊達な置賜四十八館」の通し番号（長井は14〜18）だったが、本人の決定でガイド独自の連番に付け替えた。長井市は現在の並び順に 1〜5（白山森館=1、正福寺館=2、時庭館=3、片倉館=4、横沢山館=5）。
- 元の四十八館の番号は、ガイドの表示・データから外す。本文や出典で四十八館という名鑑自体に触れることは番号とは別で、従来どおり。
- ゲーム側との共有への影響はない: 共有のキーは城館ID（slug）で、number はガイド側の表示用メタデータ。ゲーム側候補リストの通し番号は向こうの文書内の整理番号で別物。
- 表示順は number 順（build でソート）。
