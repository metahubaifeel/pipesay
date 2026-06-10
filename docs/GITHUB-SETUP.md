# GitHub 一次性配置（以后交给 Cursor Agent 代管）

你 **不用** 再把 Token 发给 AI。只需在本机做 **一次** 登录，之后说「帮我推到 GitHub」即可。

## 第一步：安装 GitHub CLI（已有可跳过）

```bash
# Ubuntu/Debian
sudo apt install gh
# 或已有：~/.local/bin/gh
```

## 第二步：登录（只需做一次）

在 **本机终端** 运行（会打开浏览器）：

```bash
gh auth login -h github.com -p https -w
```

按提示选择：

1. GitHub.com  
2. HTTPS  
3. Login with a web browser  
4. 浏览器里用 **metahubaifeel** 登录并授权  

验证：

```bash
gh auth status
# 应显示：Logged in to github.com as metahubaifeel
```

## 第三步：以后怎么用

对 Cursor 说例如：

- 「帮我把稳定版推到 GitHub」
- 「打个 tag v1.3-stable 并 push」
- 「Lab 分支也同步上去」

Agent 会用 `gh` / `git push`，**不需要** 你再发 Token。

## 仓库地址

- https://github.com/metahubaifeel/pipesay
- 稳定版：`master` 或 `v1.3-stable`
- Lab：`experiment/drag-drop`

## 安全：曾泄露的 Token 请作废

若 Token 曾出现在聊天里：

1. GitHub → Settings → Developer settings → Personal access tokens  
2. 删除旧 token（如 `autoagent`）  
3. **不要** 把新 token 贴给 AI；用上面的 `gh auth login` 即可  

## 换电脑

```bash
gh auth login          # 新电脑登录一次
git clone https://github.com/metahubaifeel/pipesay.git
cd pipesay
git checkout v1.3-stable
# 见 README.md 安装 venv 与 Soniox Key
```
