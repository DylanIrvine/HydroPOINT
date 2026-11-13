# write the results to one xlsx: Daily, Monthly, Annual, Settings

import io

import pandas as pd


def _write(writer, frame, sheet, date_columns=()):
    numeric = frame.select_dtypes('number').columns
    frame = frame.copy()
    frame[numeric] = frame[numeric].round(3)
    frame.to_excel(writer, sheet_name=sheet, index=False)
    ws = writer.sheets[sheet]
    ws.freeze_panes(1, 1)
    date_format = writer.book.add_format({'num_format': 'yyyy-mm-dd'})
    for i, column in enumerate(frame.columns):
        width = min(max(len(str(column)) + 2, 11), 45)
        ws.set_column(i, i, width, date_format if column in date_columns else None)


def build(daily, monthly, annual, settings_table):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
        _write(writer, daily, 'Daily', date_columns=('Date',))
        _write(writer, monthly, 'Monthly')
        _write(writer, annual, 'Annual', date_columns=('Start date', 'End date'))
        settings_table.to_excel(writer, sheet_name='Settings', index=False)
        ws = writer.sheets['Settings']
        ws.set_column(0, 0, 44)
        ws.set_column(1, 1, 90)
    return buffer.getvalue()
