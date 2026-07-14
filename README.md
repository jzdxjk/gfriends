# Gfriends 女友头像仓库
![TotalNumber](https://img.shields.io/badge/全部女友数-295,041-blueviolet.svg)  ![AutoUpdate](https://img.shields.io/badge/更新日期-2026--7--14-brightgreen.svg)<br>

## 本仓库非官方库，属于 Avdb 和 Emby 插件 ActorArchives 的专有仓库， 使用和浏览请确认符合当地法律规定。

## 本地更新 Filetree.json

新增、删除或重命名 `Content/` 下的头像后，可以在本地运行：

```bash
./scripts/update_filetree_local.sh
```

脚本会按 GitHub Actions 使用的格式扫描 `Content/`，更新 `Filetree.json` 的 `Content` / `Information`，并同步 README 顶部的总数和更新日期 badge。默认会保留已有条目的 `?t=` 缓存时间，只给新增条目写入当前时间；如需强制刷新全部时间戳：

```bash
./scripts/update_filetree_local.sh --refresh-timestamps
```

如果脚本提示有历史别名冲突，可追加 `--verbose` 查看具体跳过路径。

GitHub Actions 的自动更新也会调用同一个脚本，并使用浅克隆以避免拉取完整历史。
