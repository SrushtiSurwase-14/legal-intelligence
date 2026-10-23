"""Extract text from a text-based PDF so it can be added to the corpus.  (needs: pip install pypdf)

    python scripts/pdf_to_text.py input.pdf data/corpus/my_act.txt

NOT covered by automated tests. Always open the .txt and check it: scanned PDFs give no text, and
legal PDFs often need manual fixes so that headings read 'Section 4.' at the start of a line (that is what
the chunker splits on).
"""
import sys
from pypdf import PdfReader

src, dst = sys.argv[1], sys.argv[2]
text = "\n\n".join((p.extract_text() or "") for p in PdfReader(src).pages)
if len(text.strip()) < 100:
    sys.exit("Very little text extracted - the PDF is probably scanned (needs OCR). Nothing written.")
open(dst, "w", encoding="utf-8").write(text)
print(f"wrote {dst} ({len(text)} characters). Now create {dst.rsplit('.', 1)[0]}.meta.json and run validate_corpus.py")
