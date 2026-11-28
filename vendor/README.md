# Fremde Bausteine

Unverändert übernommen, damit die App ohne Nachladen aus dem Internet auskommt (alles liegt auf stufenweise.app).

| Datei | Herkunft | Lizenz |
| --- | --- | --- |
| `html2canvas.min.js` | html2canvas 1.4.1, https://github.com/niklasvh/html2canvas/releases/download/v1.4.1/html2canvas.min.js (SHA-256 e87e550794322e574a1fda0c1549a3c70dae5a93d9113417a429016838eab8cb) | MIT, `LICENSE-html2canvas.txt` |

Wird nur geladen, wenn auf iPad/iPhone ein PDF gebaut wird („Drucken (PDF)“) oder am Computer „Als PDF“ gewählt wird (Backlog W). Den PDF-Schreiber (nur JPEG-Seiten) hat Stufenweise selbst (`pdfWrite` in `index.html`, EUPL-1.2).
