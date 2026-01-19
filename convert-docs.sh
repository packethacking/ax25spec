#!/bin/sh -e

cd doc
pandoc ../src/ax.25.2.2.4_Oct_25.docx --from=docx --to=gfm --extract-media= -o ax.25.2.2.4_Oct_25.md
magick -density 300 ../src/ax.25.2.2.4_Oct_25.pdf page-images/page.png
cd ..
