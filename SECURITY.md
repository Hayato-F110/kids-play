# セキュリティの方針

キッズあそびランド（kids-play）は、個人の学習プロジェクトです。4〜8歳の子ども向けのミニアプリ集なので、子どものプライバシーと安全をいちばん大事にしています。

## 対象

| 対象 | 状態 |
|---|---|
| `main` ブランチのコード | 対象 |
| GitHub Pages の公開版（https://hayato-f110.github.io/kids-play/） | 対象 |
| GHCR のコンテナイメージ（`kids-play-api`、`kids-play-web`） | 対象 |
| Androidアプリ | 対象（ソースからビルドしたもの。リリース版は作っておらず、Google Play でも配布していません） |
| AWS 版 | 2026-10-28 に終了しました（リソースは削除済み） |

## 脆弱性の報告のしかた

脆弱性を見つけた場合は、**公開の Issue や Pull Request には書かず**、GitHub の非公開の報告の仕組みを使ってください。

1. このリポジトリの「Security」タブを開く
2. 「Report a vulnerability」を押す
3. 再現の手順、影響、見つけた版（コミット）を書く

報告には、**個人の情報（実名、写真、子どもの絵や声など）を含めないでください**。このアプリは子どものデータを端末の外に送らない設計で、開発者も受け取りません。

## 返事の目安

- 受け取りの返事：7日以内を目安にします
- 修正：個人の学習プロジェクトのため、期限は約束できません。影響が大きいものから対応します
- 修正したら、報告してくれた方の了承を得たうえで、Security Advisory として公開します

## 設計上の方針（参考）

- 子どもが描いた絵と録音した声は、端末の中（えほんは IndexedDB、おえかきで「ほぞん」した画像は端末のフォルダ）にだけ保存し、公開サーバーには送りません。サーバーへの保存は、開発者の PC の中（localhost）で動かす場合にだけ、設定で有効にできます
- 広告、解析、外部への通信はありません（CSP で通信先を自分のオリジンに限っています）
- 秘密情報はリポジトリに含めません。Secret scanning と Push protection を有効にしています
- 依存部品は Dependabot、コードは CodeQL、コンテナは Trivy で確かめています

詳しくは [docs/security/security-report.md](docs/security/security-report.md) と [docs/security/threat-model.md](docs/security/threat-model.md) を見てください。
