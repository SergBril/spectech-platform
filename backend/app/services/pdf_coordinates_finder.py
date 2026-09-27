"""
Утилита для определения координат полей в PDF-бланке.
Открывает PDF в браузере, кликаете мышкой → показывает координаты.

Использование:
    python pdf_coordinates_finder.py backend/app/services/pdf_templates/upd_blank.pdf
"""

import sys
import tempfile
import webbrowser

import fitz  # PyMuPDF


def create_coordinate_finder_pdf(source_pdf_path: str):
    """Создаёт интерактивный PDF с сеткой для определения координат."""
    doc = fitz.open(source_pdf_path)

    # Добавляем сетку на каждую страницу
    for page in doc:
        # Рисуем сетку каждые 10mm
        width = page.rect.width
        height = page.rect.height

        for x in range(0, int(width), 30):  # каждые ~10mm
            shape = page.new_shape()
            shape.draw_line(fitz.Point(x, 0), fitz.Point(x, height))
            shape.finish(color=(0.8, 0.8, 0.8), width=0.3)
            shape.insert_text(
                fitz.Point(x + 2, 10), str(x), fontsize=6, color=(0.5, 0.5, 0.5)
            )
            shape.commit()

        for y in range(0, int(height), 30):
            shape = page.new_shape()
            shape.draw_line(fitz.Point(0, y), fitz.Point(width, y))
            shape.finish(color=(0.8, 0.8, 0.8), width=0.3)
            shape.insert_text(
                fitz.Point(2, y + 10), str(y), fontsize=6, color=(0.5, 0.5, 0.5)
            )
            shape.commit()

    # Сохраняем в временный файл
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(temp_file.name)
    doc.close()

    print(f"✅ Сетка создана: {temp_file.name}")
    print("📋 Инструкция:")
    print("   1. Откройте PDF в Adobe Acrobat Reader (бесплатно)")
    print("   2. Используйте инструмент 'Измерение' (Measure)")
    print("   3. Кликните по нужной позиции → увидите координаты X, Y")
    print("   4. Запишите координаты в таблицу ниже")
    print()

    # Открываем в браузере (если есть плагин)
    webbrowser.open(f"file://{temp_file.name}")

    return temp_file.name


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python pdf_coordinates_finder.py <path_to_pdf>")
        sys.exit(1)

    create_coordinate_finder_pdf(sys.argv[1])
