import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import io


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': '-US,en;q=0.5',
}


def fit_text(draw, text, max_width, font_path="arial.ttf", start_size=100, line_spacing=10):
    font_size = start_size
    font = ImageFont.truetype(font_path, font_size)

    # Разбиваем текст на строки с учетом символов новой строки
    lines = text.split('\n')  # Разделяем текст по символам новой строки
    formatted_lines = []

    # Обрабатываем каждую строку, чтобы она влезала в максимальную ширину
    for line in lines:
        current_line = ''
        words = line.split()

        # Собираем слова в строку, проверяя на максимальную ширину
        for word in words:
            test_line = current_line + ' ' + word if current_line else word
            x1, y1, x2, y2 = draw.textbbox((0, 0), test_line, font=font)
            text_width, text_height = x2 - x1, y2 - y1

            if text_width <= max_width:
                current_line = test_line
            else:
                formatted_lines.append(current_line)
                current_line = word

        # Добавляем последнюю строку
        if current_line:
            formatted_lines.append(current_line)

    # Проверяем, помещается ли весь текст в высоту
    total_height = 0
    for line in formatted_lines:
        x1, y1, x2, y2 = draw.textbbox((0, 0), line, font=font)
        text_height = y2 - y1
        total_height += text_height + line_spacing

    # Если текст не помещается в высоту, уменьшаем размер шрифта
    while total_height > max_width:  # Условие на изменение ширины изображения
        font_size -= 2
        if font_size < 40:  # Минимальный размер шрифта
            break
        font = ImageFont.truetype(font_path, font_size)
        formatted_lines = []  # Сбрасываем строки, так как шрифт был уменьшен
        for line in lines:
            current_line = ''
            words = line.split()
            for word in words:
                test_line = current_line + ' ' + word if current_line else word
                x1, y1, x2, y2 = draw.textbbox((0, 0), test_line, font=font)
                text_width, text_height = x2 - x1, y2 - y1
                if text_width <= max_width:
                    current_line = test_line
                else:
                    formatted_lines.append(current_line)
                    current_line = word
            if current_line:
                formatted_lines.append(current_line)

        # Пересчитываем высоту текста
        total_height = 0
        for line in formatted_lines:
            x1, y1, x2, y2 = draw.textbbox((0, 0), line, font=font)
            text_height = y2 - y1
            total_height += text_height + line_spacing

    return formatted_lines, font, total_height


def create_image_with_text(text, font_path="arial.ttf", start_size=100, line_spacing=10):
    # Создаем изображение для начальной проверки ширины
    width = 2000  # начальная ширина
    image = Image.new('RGB', (width, 1), color='white')
    draw = ImageDraw.Draw(image)

    # Получаем текст, шрифт и высоту
    formatted_lines, font, text_height = fit_text(draw, text, width - 40, font_path, start_size, line_spacing)

    # Вычисляем высоту изображения в зависимости от количества строк и межстрочного интервала
    total_height = text_height + line_spacing * (len(formatted_lines) - 1)

    # Создаем изображение с подогнанными размерами
    if width >= 0 and total_height >= 0:
        image = Image.new('RGB', (width, total_height), color='white')
        draw = ImageDraw.Draw(image)

        # Начальная позиция для текста
        text_y = 20
        text_x = 20

        # Рисуем каждую строку текста с учетом межстрочного интервала
        for line in formatted_lines:
            # Рисуем строку текста
            draw.text((text_x, text_y), line, fill="black", font=font)

            # Обновляем вертикальную позицию для следующей строки с учетом межстрочного интервала
            x1, y1, x2, y2 = draw.textbbox((0, 0), line, font=font)
            text_height = y2 - y1
            text_y += text_height + line_spacing  # line_spacing уже учтен в расчете

        return image
    else:
        return False


def parse_news(mod_digit, mod_letter, non_ranges, ranges):
    def merge_ranges(ranges):
        parsed = []
        for r in ranges:
            parts = r.split('-')
            start = int(''.join(filter(str.isdigit, parts[0])))
            end = int(''.join(filter(str.isdigit, parts[1])))
            parsed.append((start, end))
        parsed.sort()

        merged = []
        for start, end in parsed:
            if not merged:
                merged.append([start, end])
            else:
                last_start, last_end = merged[-1]
                if start > last_end:
                    merged.append([start, end])
                else:
                    merged[-1][1] = max(last_end, end)

        return [f"{s}-{e}" for s, e in merged]


    def expand_ranges(ranges):
        expanded = []
        for r in ranges:
            parts = r.split('-')
            start = int(''.join(filter(str.isdigit, parts[0])))
            end = int(''.join(filter(str.isdigit, parts[1])))
            expanded.extend(range(start, end + 1))
        return expanded


    def custom_sort_key(item):
        item_str = str(item)
        num_part = ''.join(filter(str.isdigit, item_str))
        suffix = ''.join(filter(str.isalpha, item_str))
        num = int(num_part) if num_part else 0
        return (num, suffix)


    result = merge_ranges(ranges)
    all_numbers = expand_ranges(result)

    sorted_list = sorted(non_ranges + all_numbers, key=custom_sort_key)
    sorted_list = [str(item) for item in sorted_list]

    full_text = str()
    for task in sorted_list:
        url = f'https://reshak.ru/otvet/otvet_txt.php?otvet1=/spotlight9/images/module{mod_digit}/{mod_letter}/{task}'  # Замените на реальный URL
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        text_container = soup.find('div', class_="mainInfo")
        ex_cont = soup.find('h1', class_="titleh1")
        if text_container and ex_cont:
            texts = [element.get_text() for element in text_container.find_all(['div', 'h1', 'h2', 'h3', 'b'])]
            if texts:
                lines = str(texts[0]).strip()
                if '« Назад' not in lines:
                    unique_lines = []
                    seen = set()
                    for line in texts:
                        if line not in seen or re.match(r'^[1-9a-zA-Z\s]{1,2}$', line):
                            unique_lines.append(line)
                            seen.add(line)
                    clean_text = '\n'.join(unique_lines)
                    ex_cont = re.search(r'^\S+', (ex_cont.text).lstrip())
                    # clean_text = re.search(r'Решение #([\s\S]*)', clean_text, flags=re.DOTALL)
                    clean_text = re.sub(r'[\s\S]*Решение #([\s\S]+)', fr'### Решение:\1', clean_text, flags=re.DOTALL).rstrip()
                    # print(f'#{i}.', clean_text)
                    full_text += '\n' + '—' * 80 + '|'
                    full_text += (f'\n{ex_cont.group(0)} {clean_text}')

    #full_text = re.sub(r'(.{80})', r'\1\n', full_text, flags=re.DOTALL).rstrip()
    # print(full_text)
    image = create_image_with_text(full_text)
    if image:
        img_byte = io.BytesIO()
        image.save(img_byte, format="JPEG")
        img_byte.seek(0)

        return img_byte
