# 背景图(可选)

把雪地照片命名为 `bg.jpg` 放在这个目录下，页面背景会自动换成这张真实照片。
没有这个文件时，会回退到 `app/globals.css` 里用纯 CSS 画的雪面(蓝影 + 亮脊 + 雪粒反光)。

替换其他图片：改 `app/globals.css` 里 `body::before` 的 `url("/bg.jpg")`。
