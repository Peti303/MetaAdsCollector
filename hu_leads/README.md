# Kivitelező-kontaktgyűjtő (Meta Hirdetéstár, HU)

- `inditas.bat` (Windows) / `inditas.sh`: a teljes gyűjtés, Excel-kimenettel (`kontaktok_ÉÉÉÉ-HH-NN_ÓÓPP.xlsx`).
- `inditas_proba.bat`: rövid adatellenőrző próbafutás.
- `beallitasok.py`: célszámok, kulcsszavak, időszabályok, súlyok, kategóriaszűrés, szünetek.
- `naplo.txt`: a futás naplója. A `gyorsitotar/` mappa miatt egy megszakított futás 24 órán belül
  újraindítva nem kérdezi le újra a már lekért kulcsszavakat.
