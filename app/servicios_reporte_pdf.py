"""Exportación a PDF del reporte de ventas (HU08, CA08.4).

El PDF repite lo que muestra la pantalla de reportes y agrega lo que se
espera de un reporte de gestión impreso: identificación de la empresa y
logo, título, periodo y filtros aplicados, fecha y usuario que lo generó,
totales, tablas por sede, cajero, método de pago y día, y número de página.
"""
import os
from datetime import date

from flask import current_app
from fpdf import FPDF

from app.tiempo import ahora

EMPRESA = {'razon_social': 'Dino Park Perú S.A.C.', 'ruc': '20608934512'}
VERDE = (0, 81, 58)
GRIS = (61, 74, 67)

NOMBRE_RANGO = {
    'diario': 'Diario', 'semanal': 'Semanal', 'mensual': 'Mensual', 'personalizado': 'Personalizado',
}


def _dma(iso):
    """'2026-11-23' -> '23-11-2026' (formato DD-MM-AAAA del sistema)."""
    return date.fromisoformat(iso[:10]).strftime('%d-%m-%Y')


def _soles(n):
    return f'S/ {n:,.2f}'


class _PDF(FPDF):
    def __init__(self, generado):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.generado = generado
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(15, 15, 15)

    def header(self):
        logo = os.path.join(current_app.static_folder, 'img', 'Logo_dino.webp')
        if os.path.exists(logo):
            self.image(logo, x=15, y=10, h=16)
        self.set_xy(55, 11)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(*VERDE)
        self.cell(0, 6, EMPRESA['razon_social'], new_x='LMARGIN', new_y='NEXT', align='R')
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*GRIS)
        self.set_x(55)
        self.cell(0, 5, f"RUC {EMPRESA['ruc']}", new_x='LMARGIN', new_y='NEXT', align='R')
        self.set_draw_color(*VERDE)
        self.line(15, 29, 195, 29)
        self.set_y(33)

    def footer(self):
        self.set_y(-13)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*GRIS)
        self.cell(0, 5, f'Documento interno de gestión · Generado el {self.generado}', align='L')
        self.cell(0, 5, f'Página {self.page_no()} de {{nb}}', align='R')


def _tabla(pdf, titulo, cabecera, filas, anchos, alinear):
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*VERDE)
    pdf.cell(0, 8, titulo, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(228, 244, 236)
    for texto, ancho, al in zip(cabecera, anchos, alinear):
        pdf.cell(ancho, 7, texto, border='TB', align=al, fill=True)
    pdf.ln()
    pdf.set_font('Helvetica', '', 9)
    if not filas:
        pdf.cell(sum(anchos), 7, 'Sin movimientos en el periodo', border='B', align='C')
        pdf.ln()
    for i, fila in enumerate(filas):
        borde = 'B' if i == len(filas) - 1 else ''
        for texto, ancho, al in zip(fila, anchos, alinear):
            pdf.cell(ancho, 6, str(texto), border=borde, align=al)
        pdf.ln()
    pdf.ln(4)


def generar_pdf_reporte(reporte, rango, sede, usuario):
    """Devuelve los bytes del PDF del reporte que arma generar_reporte()."""
    generado = ahora().strftime('%d-%m-%Y %H:%M')
    pdf = _PDF(generado)
    pdf.set_title('Reporte de ventas · Dino Park')
    pdf.set_author(EMPRESA['razon_social'])
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(0, 33, 21)
    pdf.cell(0, 9, 'Reporte de ventas', new_x='LMARGIN', new_y='NEXT')

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(*GRIS)
    datos = [
        ('Periodo', f"{_dma(reporte['inicio'])} al {_dma(reporte['fin'])} ({NOMBRE_RANGO.get(rango, rango)})"),
        ('Sede', sede or 'Todas las sedes (consolidado)'),
        ('Generado por', f'{usuario} · {generado}'),
    ]
    for etiqueta, valor in datos:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(32, 6, f'{etiqueta}:')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, valor, new_x='LMARGIN', new_y='NEXT')
    pdf.ln(3)

    resumen = reporte['resumen']
    pdf.set_fill_color(204, 255, 229)
    pdf.set_text_color(0, 33, 21)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(90, 12, f"  Total vendido: {_soles(resumen['total'])}", fill=True)
    pdf.cell(90, 12, f"  Transacciones: {resumen['cantidad_transacciones']}", fill=True,
             new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    _tabla(pdf, 'Ventas por sede', ['Sede', 'Transacciones', 'Total'],
           [(s['sede'], s['cantidad'], _soles(s['total'])) for s in reporte['por_sede']],
           [100, 40, 40], ['L', 'R', 'R'])
    _tabla(pdf, 'Ventas por cajero', ['Cajero', 'Transacciones', 'Total'],
           [(c['cajero'], c['cantidad'], _soles(c['total'])) for c in reporte['por_cajero']],
           [100, 40, 40], ['L', 'R', 'R'])
    _tabla(pdf, 'Ventas por método de pago', ['Método', 'Transacciones', 'Total'],
           [(m['metodo_pago'].capitalize(), m['cantidad'], _soles(m['total'])) for m in reporte['por_metodo']],
           [100, 40, 40], ['L', 'R', 'R'])
    _tabla(pdf, 'Ventas por día', ['Fecha', 'Total'],
           [(_dma(d['fecha']), _soles(d['total'])) for d in reporte['por_dia']],
           [100, 80], ['L', 'R'])

    return bytes(pdf.output())
