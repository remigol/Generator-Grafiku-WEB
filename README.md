# Generator Grafiku WEB v1

Osobna aplikacja do tworzenia grafiku dla 9 pracowników (A–F produkcja, G–I pakowanie). Eksport XLSX jest przeznaczony do ręcznego importu w ShiftMate, ale format importu musi zostać zweryfikowany.

## Uruchomienie lokalne
```bash
pip install -r requirements.txt
python server.py
```
Otwórz http://localhost:8000.

## Render
W Render wybierz **New → Blueprint**, połącz repozytorium `remigol/Generator-Grafiku-WEB` i zatwierdź konfigurację `render.yaml`. Serwis używa zmiennej `PORT` dostarczanej przez Render. Po wdrożeniu sprawdź generowanie, walidację i pobranie pliku XLSX.

## Obecne zasady
- Zmiany 6/18, bez pracy w niedziele i święta; sobota tylko 6.
- Obsada 2–3 osoby na zmianie w dni powszednie, dokładnie 2 w sobotę.
- Minimum 1 pracownik produkcji i maksymalnie 2 z pakowania na zmianie.
- Maksymalnie 4 dni pracy z rzędu, minimum 2 dni wolne po bloku.
- Bez zmiany 6/18 wewnątrz bloku.
- Indywidualne ograniczenie E: bez porannej zmiany w pierwszych dwóch dniach, maks. 3 noce z rzędu.
- Ręczne blokady 6/18/W; edycja komórek, cofanie, zapis/wczytanie JSON, eksport XLSX.

## Znane ograniczenia v1
- Minimalny blok 3 dni pracy nie jest jeszcze twardo egzekwowany.
- Równowaga godzin, rotacja i różnice między blokami nie są jeszcze w pełni optymalizowane.
- Walidacja nie obejmuje wszystkich indywidualnych reguł ani nominalnych godzin.
- Zmiany w obrębie miesiąca nie uwzględniają automatycznie bloków z poprzedniego miesiąca.
- Import XLSX do ShiftMate nie został jeszcze przetestowany.
- Aplikacja nie wymaga logowania, więc nie należy wprowadzać danych osobowych.
