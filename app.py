import os
import csv
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'prec-reg-secret-key-2024-alameda'

CSV_PATH = os.path.join(os.path.dirname(__file__), 'prec.csv')
PRECURSORES_CSV = os.path.join(os.path.dirname(__file__), 'precursores.csv')

MESES_ORDER = [
    'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto'
]

PASSWORD_ADMIN = 'alameda2024'
PASSWORD_INVITADO = 'invitado2024'
META_ANUAL = 600
META_MENSUAL = 50
MAX_TOTAL = 55

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('autenticado'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('autenticado'):
            return redirect(url_for('login', next=request.path))
        if session.get('rol') != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def cargar_precursores_meta():
    rows = []
    if not os.path.exists(PRECURSORES_CSV):
        return rows
    with open(PRECURSORES_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            rows.append({
                'nombre': r['Nombre'].strip(),
                'fecha_nombramiento': r.get('FechaNombramiento', '').strip(),
            })
    return rows

def guardar_precursores_meta(rows):
    with open(PRECURSORES_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Nombre', 'FechaNombramiento'])
        for r in rows:
            writer.writerow([r['nombre'], r['fecha_nombramiento']])

def calcular_anios_nombramiento(fecha_str):
    if not fecha_str:
        return None
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
        hoy = datetime.now()
        anios = hoy.year - fecha.year
        if (hoy.month, hoy.day) < (fecha.month, fecha.day):
            anios -= 1
        return anios
    except (ValueError, TypeError):
        return None

def obtener_fecha_nombramiento(nombre):
    meta = cargar_precursores_meta()
    for r in meta:
        if r['nombre'] == nombre:
            return r['fecha_nombramiento']
    return ''

def cargar_datos():
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            rows.append({
                'anio': int(r['Año Servicio']),
                'nombre': r['Nombre'].strip(),
                'mes': r['Mes'].strip(),
                'horas': int(r['Horas']) if r['Horas'].strip() else 0,
                'servicio_sagrado': int(r['Servicio Sagrado']) if r['Servicio Sagrado'].strip() else 0,
                'total_mes': int(r['Total Mes']) if r['Total Mes'].strip() else 0,
                'faltante_mes': int(r['Faltante Mes']) if r['Faltante Mes'].strip() else 0,
            })
    return rows

def guardar_datos(rows):
    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Año Servicio', 'Nombre', 'Mes', 'Horas', 'Servicio Sagrado', 'Total Mes', 'Faltante Mes'])
        for r in rows:
            writer.writerow([
                r['anio'], r['nombre'], r['mes'],
                r['horas'] if r['horas'] else '',
                r['servicio_sagrado'] if r['servicio_sagrado'] else '',
                r['total_mes'], r['faltante_mes']
            ])

def determinar_anio_servicio(mes):
    return 2026 if mes in ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto') else 2025

def servicio_anio_inicio(anio, mes):
    if mes in ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto'):
        return anio - 1
    return anio

def obtener_precursores(rows):
    precursores = {}
    for r in rows:
        nom = r['nombre']
        if nom not in precursores:
            precursores[nom] = []
        precursores[nom].append(r)
    return precursores

def obtener_servicio_anio_actual(registros):
    if not registros:
        return 2025
    return max(servicio_anio_inicio(r['anio'], r['mes']) for r in registros)

def calcular_progreso_anual(registros, servicio_anio_inicio_val):
    filtrados = [r for r in registros
                 if servicio_anio_inicio(r['anio'], r['mes']) == servicio_anio_inicio_val]
    filtrados.sort(key=lambda x: MESES_ORDER.index(x['mes']))
    total_horas = sum(r['total_mes'] for r in filtrados)
    meses_completados = len(filtrados)
    faltante = META_ANUAL - total_horas
    meses_restantes = 12 - meses_completados
    necesita_por_mes = round(faltante / meses_restantes, 1) if meses_restantes > 0 else 0
    return {
        'total_horas': total_horas,
        'meta_anual': META_ANUAL,
        'progreso_pct': round((total_horas / META_ANUAL) * 100, 1),
        'faltante': faltante,
        'meses_completados': meses_completados,
        'meses_restantes': meses_restantes,
        'promedio_mensual': round(total_horas / meses_completados, 1) if meses_completados > 0 else 0,
        'necesita_por_mes': necesita_por_mes,
    }


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        pwd = request.form.get('password')
        if pwd == PASSWORD_ADMIN:
            session['autenticado'] = True
            session['rol'] = 'admin'
            next_page = request.args.get('next', '/')
            return redirect(next_page)
        elif pwd == PASSWORD_INVITADO:
            session['autenticado'] = True
            session['rol'] = 'invitado'
            next_page = request.args.get('next', '/')
            return redirect(next_page)
        error = 'Contraseña incorrecta'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('autenticado', None)
    session.pop('rol', None)
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    rows = cargar_datos()
    precursores = obtener_precursores(rows)
    nombres = sorted(precursores.keys())
    prec_meta = {p['nombre']: p['fecha_nombramiento'] for p in cargar_precursores_meta()}

    resumen_global = []
    for nom in nombres:
        regs = precursores[nom]
        serv_inicio = obtener_servicio_anio_actual(regs)
        prog = calcular_progreso_anual(regs, serv_inicio)
        ultimo = [r for r in regs
                  if servicio_anio_inicio(r['anio'], r['mes']) == serv_inicio
                  and r['mes'] in MESES_ORDER]
        ultimo.sort(key=lambda x: MESES_ORDER.index(x['mes']))
        ult_reg = ultimo[-1] if ultimo else None
        resumen_global.append({
            'nombre': nom,
            'fecha_nombramiento': prec_meta.get(nom, ''),
            'anios_nombramiento': calcular_anios_nombramiento(prec_meta.get(nom, '')),
            'total_horas': prog['total_horas'],
            'progreso_pct': prog['progreso_pct'],
            'faltante': prog['faltante'],
            'meta_anual': META_ANUAL,
            'promedio_mensual': prog['promedio_mensual'],
            'meses_completados': prog['meses_completados'],
            'meses_restantes': prog['meses_restantes'],
            'necesita_por_mes': prog['necesita_por_mes'],
            'anio_servicio': serv_inicio,
            'ultimo_mes': ult_reg['mes'] if ult_reg else '',
            'ultimo_total': ult_reg['total_mes'] if ult_reg else 0,
        })

    resumen_global.sort(key=lambda x: x['progreso_pct'], reverse=True)

    return render_template('index.html',
                         precursores=resumen_global,
                         nombres=nombres,
                         meta_anual=META_ANUAL,
                         meta_mensual=META_MENSUAL,
                         max_total=MAX_TOTAL,
                         meses=MESES_ORDER,
                         rol=session.get('rol', 'invitado'))


@app.route('/api/precursor/<nombre>')
@login_required
def api_precursor(nombre):
    rows = cargar_datos()
    registros = [r for r in rows if r['nombre'] == nombre]
    serv_inicio = obtener_servicio_anio_actual(registros)
    prog = calcular_progreso_anual(registros, serv_inicio)

    registros_anio = sorted(
        [r for r in registros if servicio_anio_inicio(r['anio'], r['mes']) == serv_inicio],
        key=lambda x: MESES_ORDER.index(x['mes'])
    )

    meses_data = []
    for m in MESES_ORDER:
        encontrado = [r for r in registros_anio if r['mes'] == m]
        if encontrado:
            r = encontrado[0]
            meses_data.append({
                'mes': m, 'horas': r['horas'],
                'servicio_sagrado': r['servicio_sagrado'],
                'total': r['total_mes'], 'faltante': r['faltante_mes']
            })
        else:
            meses_data.append({
                'mes': m, 'horas': 0, 'servicio_sagrado': 0,
                'total': 0, 'faltante': -META_MENSUAL
            })

    fecha_nombramiento = obtener_fecha_nombramiento(nombre)
    return jsonify({
        'nombre': nombre,
        'fecha_nombramiento': fecha_nombramiento,
        'anios_nombramiento': calcular_anios_nombramiento(fecha_nombramiento),
        'anio_servicio': serv_inicio,
        'progreso': prog,
        'meses': meses_data
    })


@app.route('/api/resumen')
@login_required
def api_resumen():
    rows = cargar_datos()
    precursores = obtener_precursores(rows)

    stats = {'al_dia': 0, 'abajo': 0, 'total': 0, 'suma_horas': 0}
    detalles = []
    for nom, regs in precursores.items():
        serv_inicio = obtener_servicio_anio_actual(regs)
        prog = calcular_progreso_anual(regs, serv_inicio)
        stats['total'] += 1
        stats['suma_horas'] += prog['total_horas']
        if prog['promedio_mensual'] >= META_MENSUAL:
            stats['al_dia'] += 1
        else:
            stats['abajo'] += 1
        detalles.append({'nombre': nom, **prog})

    stats['promedio_general'] = round(stats['suma_horas'] / stats['total'], 1) if stats['total'] else 0
    return jsonify({'stats': stats, 'detalles': detalles})


@app.route('/registrar', methods=['GET', 'POST'])
@admin_required
def registrar():
    rows = cargar_datos()
    precursores = obtener_precursores(rows)
    nombres_csv = set(precursores.keys())
    meta_nombres = {p['nombre'] for p in cargar_precursores_meta()}
    nombres = sorted(nombres_csv | meta_nombres)

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        mes = request.form['mes'].strip()
        horas = int(request.form.get('horas', 0) or 0)
        servicio_sagrado = int(request.form.get('servicio_sagrado', 0) or 0)
        total_mes = horas + servicio_sagrado
        faltante = total_mes - META_MENSUAL
        anio_servicio = determinar_anio_servicio(mes)

        if servicio_sagrado > 0 and total_mes > MAX_TOTAL:
            return render_template('registrar.html', nombres=nombres, meses=MESES_ORDER,
                                 meta_mensual=META_MENSUAL, max_total=MAX_TOTAL,
                                 prec_meta=meta_nombres, error=f'Al reportar Servicio Sagrado, el total ({total_mes}h) no puede superar las {MAX_TOTAL}h.')

        existe = False
        for r in rows:
            if r['nombre'] == nombre and r['mes'] == mes and r['anio'] == anio_servicio:
                r['horas'] = horas
                r['servicio_sagrado'] = servicio_sagrado
                r['total_mes'] = total_mes
                r['faltante_mes'] = faltante
                existe = True
                break

        if not existe:
            rows.append({
                'anio': anio_servicio,
                'nombre': nombre,
                'mes': mes,
                'horas': horas,
                'servicio_sagrado': servicio_sagrado,
                'total_mes': total_mes,
                'faltante_mes': faltante,
            })

        guardar_datos(rows)
        return redirect(url_for('index'))

    return render_template('registrar.html', nombres=nombres, meses=MESES_ORDER,
                         meta_mensual=META_MENSUAL, max_total=MAX_TOTAL,
                         prec_meta=meta_nombres, error='')


@app.route('/editar/<nombre>/<mes>/<int:anio>', methods=['GET', 'POST'])
@admin_required
def editar(nombre, mes, anio):
    rows = cargar_datos()
    precursores = obtener_precursores(rows)
    nombres_csv = set(precursores.keys())
    meta_nombres = {p['nombre'] for p in cargar_precursores_meta()}
    nombres = sorted(nombres_csv | meta_nombres)
    registro = None
    for r in rows:
        if r['nombre'] == nombre and r['mes'] == mes and r['anio'] == anio:
            registro = r
            break

    if request.method == 'POST':
        horas = int(request.form.get('horas', 0) or 0)
        servicio_sagrado = int(request.form.get('servicio_sagrado', 0) or 0)
        total_mes = horas + servicio_sagrado
        faltante = total_mes - META_MENSUAL

        if servicio_sagrado > 0 and total_mes > MAX_TOTAL:
            return render_template('registrar.html', nombres=nombres, meses=MESES_ORDER,
                                 meta_mensual=META_MENSUAL, max_total=MAX_TOTAL,
                                 editando=registro, prec_meta=meta_nombres,
                                 error=f'Al reportar Servicio Sagrado, el total ({total_mes}h) no puede superar las {MAX_TOTAL}h.')

        if registro:
            registro['horas'] = horas
            registro['servicio_sagrado'] = servicio_sagrado
            registro['total_mes'] = total_mes
            registro['faltante_mes'] = faltante
        guardar_datos(rows)
        return redirect(url_for('index'))

    return render_template('registrar.html', nombres=nombres, meses=MESES_ORDER,
                         meta_mensual=META_MENSUAL, max_total=MAX_TOTAL,
                         editando=registro, prec_meta=meta_nombres, error='')


@app.route('/nuevo-precursor', methods=['GET', 'POST'])
@admin_required
def nuevo_precursor():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        fecha = request.form.get('fecha_nombramiento', '').strip()

        meta_rows = cargar_precursores_meta()
        existe = any(r['nombre'] == nombre for r in meta_rows)
        if not existe:
            meta_rows.append({'nombre': nombre, 'fecha_nombramiento': fecha})
            guardar_precursores_meta(meta_rows)
        else:
            for r in meta_rows:
                if r['nombre'] == nombre and fecha:
                    r['fecha_nombramiento'] = fecha
            guardar_precursores_meta(meta_rows)

        return redirect(url_for('index'))

    return render_template('nuevo_precursor.html')


@app.route('/precursor/<nombre>/editar-fecha', methods=['GET', 'POST'])
@admin_required
def editar_fecha_precursor(nombre):
    meta_rows = cargar_precursores_meta()
    registro = None
    for r in meta_rows:
        if r['nombre'] == nombre:
            registro = r
            break

    if request.method == 'POST':
        fecha = request.form.get('fecha_nombramiento', '').strip()
        if registro:
            registro['fecha_nombramiento'] = fecha
        else:
            meta_rows.append({'nombre': nombre, 'fecha_nombramiento': fecha})
        guardar_precursores_meta(meta_rows)
        return redirect(url_for('index'))

    return render_template('nuevo_precursor.html',
                         editando_nombre=nombre,
                         fecha_actual=registro['fecha_nombramiento'] if registro else '')


@app.route('/reporte/<nombre>/pdf')
@login_required
def reporte_pdf(nombre):
    rows = cargar_datos()
    registros = [r for r in rows if r['nombre'] == nombre]
    serv_inicio = obtener_servicio_anio_actual(registros)
    prog = calcular_progreso_anual(registros, serv_inicio)

    registros_anio = sorted(
        [r for r in registros if servicio_anio_inicio(r['anio'], r['mes']) == serv_inicio],
        key=lambda x: MESES_ORDER.index(x['mes'])
    )

    fecha_nombramiento = obtener_fecha_nombramiento(nombre)

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- Header ---
    pdf.set_fill_color(26, 35, 126)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_xy(10, 8)
    pdf.cell(0, 10, 'Seguimiento Actividad Precursores', align='C')
    pdf.set_font('Helvetica', '', 11)
    pdf.set_xy(10, 20)
    pdf.cell(0, 8, 'Alameda Del Rio', align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_xy(10, 30)
    pdf.cell(0, 6, f'Ano Servicio {serv_inicio+1}', align='C')

    # --- Precursor Info ---
    pdf.ln(45)
    pdf.set_text_color(26, 35, 126)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, nombre)
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(100, 100, 100)
    if fecha_nombramiento:
        anios = calcular_anios_nombramiento(fecha_nombramiento)
        txt = f'Nombramiento: {fecha_nombramiento}'
        if anios is not None:
            txt += f'  ({anios} {"ano" if anios == 1 else "anos"} de nombrado)'
        pdf.cell(0, 6, txt)
        pdf.ln(6)

    # --- Summary Cards ---
    pdf.ln(5)
    card_y = pdf.get_y()
    card_data = [
        ('Total Horas', str(prog['total_horas']), '26,35,126'),
        ('Meta', f"{prog['meta_anual']}h", '46,125,50'),
        ('Faltante', str(prog['faltante']) + 'h', '198,40,40'),
        ('Prom./Mes', str(prog['promedio_mensual']), '245,124,0'),
        ('Necesita/mes', str(prog['necesita_por_mes']), '26,35,126'),
        ('Restan', str(prog['meses_restantes']) + ' meses', '100,100,100'),
    ]

    start_x = 10
    card_w = 30
    card_h = 22
    gap = 3
    total_w = len(card_data) * (card_w + gap) - gap
    offset = (190 - total_w) / 2

    for i, (label, value, color) in enumerate(card_data):
        x = start_x + offset + i * (card_w + gap)
        y = card_y
        r, g, b = [int(c) for c in color.split(',')]
        pdf.set_draw_color(r, g, b)
        pdf.set_line_width(0.5)
        pdf.rect(x, y, card_w, card_h)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(120, 120, 120)
        pdf.set_xy(x, y + 3)
        pdf.cell(card_w, 5, label, align='C')
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(r, g, b)
        pdf.set_xy(x, y + 9)
        pdf.cell(card_w, 8, value, align='C')

    pdf.set_y(card_y + card_h + 8)

    # --- Progress Bar ---
    bar_y = pdf.get_y()
    bar_w = 170
    bar_h = 8
    pdf.set_fill_color(230, 230, 230)
    pdf.rect(20, bar_y, bar_w, bar_h, 'F')
    pct = min(prog['progreso_pct'], 100) / 100
    if pct > 0:
        bar_color = (46, 125, 50) if pct >= 0.5 else (245, 124, 0) if pct >= 0.3 else (198, 40, 40)
        pdf.set_fill_color(*bar_color)
        pdf.rect(20, bar_y, bar_w * pct, bar_h, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_xy(20, bar_y + 0.5)
    pdf.cell(bar_w, bar_h - 1, f'  {prog["progreso_pct"]}%', align='L')
    pdf.set_text_color(80, 80, 80)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_xy(20, bar_y + bar_h + 1)
    pdf.cell(bar_w, 4, f'Progreso: {prog["total_horas"]}h de {prog["meta_anual"]}h  |  {prog["meses_completados"]} de 12 meses', align='C')

    pdf.set_y(bar_y + bar_h + 10)

    # --- Monthly Table ---
    pdf.set_fill_color(26, 35, 126)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    col_w = [36, 28, 28, 28, 28, 35]
    headers = ['Mes', 'Horas', 'S. Sagrado', 'Total', '+/- Meta', 'Estado']
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align='C')
    pdf.ln()

    for row_idx, m in enumerate(MESES_ORDER):
        encontrado = [r for r in registros_anio if r['mes'] == m]
        if encontrado:
            r = encontrado[0]
            h, ss, tot, falt = r['horas'], r['servicio_sagrado'], r['total_mes'], r['faltante_mes']
        else:
            h, ss, tot, falt = 0, 0, 0, -META_MENSUAL

        hay_registro = encontrado and (h > 0 or ss > 0)
        status = 'OK' if hay_registro else 'Pendiente'
        if row_idx % 2 == 0:
            pdf.set_fill_color(245, 245, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(50, 50, 50)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(col_w[0], 6, m, border=1, align='C', fill=True)
        pdf.cell(col_w[1], 6, str(h) if h else '-', border=1, align='C', fill=True)
        pdf.cell(col_w[2], 6, str(ss) if ss else '-', border=1, align='C', fill=True)
        pdf.cell(col_w[3], 6, str(tot) if tot else '-', border=1, align='C', fill=True)
        pdf.set_text_color(46, 125, 50) if falt >= 0 else pdf.set_text_color(198, 40, 40)
        pdf.cell(col_w[4], 6, f"+{falt}" if falt > 0 else str(falt), border=1, align='C', fill=True)
        pdf.set_text_color(46, 125, 50) if status == 'OK' else pdf.set_text_color(198, 40, 40)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(col_w[5], 6, status, border=1, align='C', fill=True)
        pdf.ln()

    # --- Footer Totals ---
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(26, 35, 126)
    pdf.cell(0, 7, f'Total acumulado: {prog["total_horas"]}h de {prog["meta_anual"]}h', align='R')

    # --- Footer ---
    pdf.set_y(-15)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} - Seguimiento Actividad Precursores Alameda Del Rio', align='C')

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    filename = f'reporte_{nombre.replace(" ", "_")}_{serv_inicio+1}.pdf'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/reporte-anual')
@login_required
def reporte_anual():
    rows = cargar_datos()
    precursores = obtener_precursores(rows)
    prec_meta = {p['nombre']: p['fecha_nombramiento'] for p in cargar_precursores_meta()}

    anio_servicio = 2026

    cumplieron = []
    umbral = []
    no_cumplieron = []

    for nom, regs in precursores.items():
        regs_anio = [r for r in regs if servicio_anio_inicio(r['anio'], r['mes']) == anio_servicio]
        if not regs_anio:
            continue

        total_horas = sum(r['total_mes'] for r in regs_anio)
        meses_completados = len(regs_anio)
        promedio = round(total_horas / meses_completados, 1) if meses_completados > 0 else 0

        entry = {
            'nombre': nom,
            'total_horas': total_horas,
            'meta_anual': META_ANUAL,
            'progreso_pct': round((total_horas / META_ANUAL) * 100, 1),
            'promedio_mensual': promedio,
            'meses_completados': meses_completados,
            'fecha_nombramiento': prec_meta.get(nom, ''),
            'anios_nombramiento': calcular_anios_nombramiento(prec_meta.get(nom, '')),
            'faltante': META_ANUAL - total_horas,
        }

        if total_horas >= META_ANUAL:
            cumplieron.append(entry)
        elif total_horas >= 560:
            umbral.append(entry)
        else:
            no_cumplieron.append(entry)

    cumplieron.sort(key=lambda x: x['total_horas'], reverse=True)
    umbral.sort(key=lambda x: x['total_horas'], reverse=True)
    no_cumplieron.sort(key=lambda x: x['total_horas'], reverse=True)

    return render_template('reporte_anual.html',
                         cumplieron=cumplieron,
                         umbral=umbral,
                         no_cumplieron=no_cumplieron,
                         anio_servicio=anio_servicio,
                         meta_anual=META_ANUAL,
                         rol=session.get('rol', 'invitado'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
