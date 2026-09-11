# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

def validate_org_file(file_path: Path) -> Tuple[bool, List[str], Optional[pd.DataFrame]]:
    errors = []
    try:
        df = pd.read_excel(file_path, header=0)
    except Exception as e:
        errors.append(f"Не удалось прочитать файл Excel: {str(e)}")
        return False, errors, None

    if df.shape[1] != 4:
        errors.append(
            f"Файл организации должен содержать 4 столбца. Найдено {df.shape[1]} столбцов, смотрите шаблон."
        )
    if errors:
        return False, errors, None

    expected_columns = ["№ п/п", "Наименование данных", "Данные организации"]
    for i, expected_col in enumerate(expected_columns):
        actual_col = str(df.columns[i]).strip()
        if actual_col != expected_col:
            errors.append(
                f"Название столбца {i + 1} не соответствует шаблону. Ожидается: \"{expected_col}\", найдено: \"{actual_col}\"."
            )
    if errors:
        return False, errors, None

    expected_rows = {
        0: [1, 'Полное наименование организации'],
        1: [2, 'Сокращенное наименование организации'],
        2: [3, 'Код причины постановки на учёт (КПП)'],
        3: [4, 'Идентификационный номер налогоплательщика (ИНН)'],
        4: [5, 'Код работодателя по ОКПО'],
        5: [6, 'Код органа государственной власти по ОКОГУ'],
        6: [7, 'Код основного вида экономической деятельности работодателя ОКВЭД'],
        7: [8, 'Код территории по ОКТМО'],
        8: [9, 'Юридический адрес организации'],
        9: [10, 'Аудитор (должность, Ф.И.О. полностью)', 'Должность', 'Ф.И.О.'],
        11: [11, 'Руководитель организации (должность, Ф.И.О. полностью)', 'Должность', 'Ф.И.О.'],
        13: [12,
             'Председатель рабочей группы по проведению оценки профессиональных рисков (должность, Ф.И.О. полностью)',
             'Должность', 'Ф.И.О.'],
        15: [13, 'Члены рабочей группы по проведению оценки профессиональных рисков (должность, Ф.И.О. полностью)',
             'Должность', 'Ф.И.О.'],
    }

    for i, row in enumerate(df.itertuples(index=False)):
        if i == 10 or i == 12 or i == 14 or i > 15:
            continue
        expected_num = expected_rows[i][0]
        expected_name = expected_rows[i][1]
        row_idx = row[0]
        row_name = row[1]
        try:
            actual_num = int(float(row_idx))
        except (ValueError, TypeError):
            errors.append(
                f"Ошибка в нумерации: в строке {expected_num} в столбце \"№ п/п\" найдено нечисловое значение: \"{row_idx}\"."
            )
            continue
        if actual_num != expected_num:
            errors.append(f"Ошибка в нумерации: ожидался номер {expected_num}, найден {actual_num}.")
        if pd.isna(row_name):
            errors.append(
                f"В строке {expected_num} название данных отсутствует (пустая ячейка). Ожидается: \"{expected_rows[i][1]}\"."
            )
            continue
        if row_name != expected_name:
            errors.append(
                f"В строке {expected_num} ожидалось \"{expected_rows[i][1]}\", найдено \"{row_name}\"."
            )
        if i > 8:
            dop_cols = [row[2], row[3]]
            for j in range(2):
                col = dop_cols[j]
                if pd.isna(col):
                    errors.append(
                        f"В строке {expected_num} отсутствует столбец для должности. Ожидается: \"{expected_rows[i][j + 2]}\"."
                    )
                if col != expected_rows[i][j + 2]:
                    errors.append(
                        f"Ошибка в строке {expected_num}: ожидался столбец: \"{expected_rows[i][j + 2]}\", найден \"{col}\"."
                    )
    if errors:
        return False, errors, None
    return True, [], df


def validate_people_file(file_path: Path) -> Tuple[bool, List[str], Optional[pd.DataFrame]]:
    errors = []
    try:
        df = pd.read_excel(file_path, header=0)
    except Exception as e:
        errors.append(f"Не удалось прочитать файл Excel: {str(e)}")
        return False, errors, None

    if df.shape[1] != 8:
        errors.append(
            f"Файл с сотрудниками должен содержать 8 столбцов. Найдено {df.shape[1]} столбцов, смотрите шаблон."
        )
    if errors:
        return False, errors, None

    expected_columns = [
        "№ п/п (№ рабочего места, по ранее проведенной СОУТ/АРМ))",
        "Наименование профессии или должности (специальности)",
        "Количество работающих на рабочем месте",
        "Из них женщин",
        "Из них несовершеннолетних",
        "Из них инвалидов",
        "Используемое оборудование",
        "Применяемые сырье и материалы",
    ]
    for i, expected_col in enumerate(expected_columns):
        actual_col = str(df.columns[i]).strip()
        if actual_col != expected_col:
            errors.append(f"Название столбца {i + 1} не соответствует шаблону. Ожидается: \"{expected_col}\", найдено: \"{actual_col}\".")
    if errors:
        return False, errors, None

    worker_ids = dict()
    cur_number = 1
    for i, row in enumerate(df.itertuples(index=False)):
        if row[1] == "Подразделение":
            div_level = row[0]
            if not isinstance(div_level, str):
                try:
                    float(div_level)
                except Exception:
                    errors.append(
                        f"Неопознанный символ \"{div_level}\" в маркере подразделения строки {i + 2}. "
                        f"Допускаются только маркеры-цифры"
                    )
            try:
                if int(float(div_level)) != float(div_level):
                    errors.append(
                        f"Неопознанный символ \"{div_level}\" в маркере подразделения строки {i + 2}. "
                        f"Допускаются только целочисленные маркеры"
                    )
            except (ValueError, TypeError):
                pass
        else:
            cur_worker_id = row[0]
            cur_worker_position = row[1]
            if pd.isna(cur_worker_id):
                cur_worker_id = str(cur_number)
                cur_number += 1
                if cur_worker_id in worker_ids.keys():
                    errors.append(
                        f"Из-за совместного использования явной и неявной нумерации у сотрудника {cur_worker_position} и {worker_ids[cur_worker_id]} совпадают ID ({cur_worker_id})."
                        f"Пожалуйста, исправьте ID сотрудников и попробуйте снова."
                    )
                else:
                    worker_ids[cur_worker_id] = cur_worker_position
            else:
                cur_worker_id = str(cur_worker_id).strip()
                if cur_worker_id in worker_ids.keys():
                    errors.append(
                        f"У сотрудника {cur_worker_position} и {worker_ids[cur_worker_id]} совпадают ID ({cur_worker_id})."
                        f"Пожалуйста, исправьте ID сотрудников и попробуйте снова."
                    )
                else:
                    worker_ids[cur_worker_id] = cur_worker_position
    if errors:
        return False, errors, None
    return True, [], df


def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
    if not date_str or not date_str.strip():
        return False, "Дата не может быть пустой."
    date_str = date_str.strip()
    try:
        parsed_date = datetime.strptime(date_str, "%d.%m.%Y")
        current_year = datetime.now().year
        if parsed_date.year < 2000:
            return False, f"Год не может быть меньше 2000. Указан год: {parsed_date.year}."
        if parsed_date.year > current_year + 5:
            return False, f"Год не может быть больше {current_year + 5}. Указан год: {parsed_date.year}."
        return True, None
    except ValueError:
        return False, f"Неверный формат даты. Ожидается ДД.ММ.ГГГГ, вместо: \"{date_str}\"."


def _s(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def parse_people_data(df: pd.DataFrame) -> List[dict]:
    df = df.fillna(int(0))
    workers: List[dict] = []
    div: List[str] = []
    level: List[float] = []
    worker_number = 1

    for _, row in df.iterrows():
        val = row.iloc[0]
        if row.iloc[1] == "Подразделение":
            if not level:
                level.append(float(row.iloc[0]))
                div.append(str(row.iloc[2]))
            else:
                while len(level) > 0 and level[-1] >= float(row.iloc[0]):
                    level = level[:-1]
                    div = div[:-1]
                div.append(str(row.iloc[2]))
                level.append(float(row.iloc[0]))
        else:
            worker_id = None
            if pd.notna(val):
                if val == 0:
                    worker_id = str(worker_number)
                    worker_number += 1
                else:
                    worker_id = str(val)
            workers.append({
                "ID": str(worker_id),
                "position": str(row.iloc[1]).strip(),
                "division": div[:],
                "number_at_workplace": int(row.iloc[2]),
                "woman": int(row.iloc[3]),
                "minors": int(row.iloc[4]),
                "disabled": int(row.iloc[5]),
                "equipment": str(row.iloc[6]).strip(),
                "materials": str(row.iloc[7]).strip(),
            })
    return workers


def parse_org_data(df: pd.DataFrame) -> dict:
    df = df.dropna(how="all")
    df = df.drop(df.columns[0], axis=1)

    def get_val(row_idx: int) -> str:
        val = df.iloc[row_idx, 1]
        if pd.isna(val):
            return ""
        return str(val).strip().replace('.0', '')

    org = {
        "full_name": get_val(0),
        "short_name": get_val(1),
        "kpp": get_val(2),
        "inn": get_val(3),
        "okpo": get_val(4),
        "okogy": get_val(5),
        "okved": get_val(6),
        "oktmo": get_val(7),
        "address": get_val(8),
        "auditor_pos": _s(df.iloc[10, 1]),
        "auditor_name": _s(df.iloc[10, 2]),
        "leader_pos": _s(df.iloc[12, 1]),
        "leader_name": _s(df.iloc[12, 2]),
        "chairman_pos": _s(df.iloc[14, 1]),
        "chairman_name": _s(df.iloc[14, 2]),
    }

    poses: List[str] = []
    names: List[str] = []
    start_idx = 16
    while start_idx < len(df):
        pos = df.iloc[start_idx, 1]
        name = df.iloc[start_idx, 2]
        pos_empty = pd.isna(pos) or (isinstance(pos, str) and pos.strip() == "")
        name_empty = pd.isna(name) or (isinstance(name, str) and name.strip() == "")
        if pos_empty and name_empty:
            break
        poses.append(_s(pos))
        names.append(_s(name))
        start_idx += 1

    org["chairmen_poses"] = poses
    org["chairmen_names"] = names
    return org