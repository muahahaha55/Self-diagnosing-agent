#!/usr/bin/env bash
# Build BeliefEffect_Mismatch.pdf. Manual thebibliography, so no bibtex pass.
cd "$(dirname "$0")" || exit 1
mkdir -p build
for i in 1 2 3; do
  pdflatex -interaction=nonstopmode -output-directory=build \
    BeliefEffect_Mismatch.tex > "build/pass$i.log" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "!! pdflatex pass $i exited $rc"
    grep -nE "^!" "build/pass$i.log" | head
    exit $rc
  fi
done
cp build/BeliefEffect_Mismatch.pdf BeliefEffect_Mismatch.pdf
echo "== pages / metadata =="
pdfinfo build/BeliefEffect_Mismatch.pdf | grep -E "Pages|Title|Author|Keywords"
echo "== undefined refs / citations (pass3) =="
grep -iE "undefined|multiply defined|may have changed" build/pass3.log || echo "  none"
echo "== overfull / underfull hboxes (pass3) =="
echo "  overfull:  $(grep -cE 'Overfull \\hbox' build/pass3.log)"
echo "  underfull: $(grep -cE 'Underfull \\hbox' build/pass3.log)"
echo "== log 'undefined' in .log =="
grep -ci "undefined" build/BeliefEffect_Mismatch.log
