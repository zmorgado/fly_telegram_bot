from statistics import mean, median, stdev
from collections import defaultdict
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

def plot_and_save(prices, dates, dest, month, airline, outdir):
    """
    Genera y guarda los gráficos relevantes para los precios de un destino/mes.
    Devuelve una lista de (filepath, descripcion) para insertar en el PDF.
    """
    imgs = []
    x = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
    y = prices
    # Bar plot: precios por fecha
    plt.figure(figsize=(8,3))
    plt.bar(x, y, color='skyblue')
    plt.title(f"Precios por fecha - {airline} {dest} {month}")
    plt.ylabel("Precio ($)")
    plt.xlabel("Fecha")
    plt.xticks(rotation=45)
    plt.tight_layout()
    bar_path = os.path.join(outdir, f"bar_{airline}_{dest}_{month}.png")
    plt.savefig(bar_path)
    plt.close()
    imgs.append((bar_path, "Distribución de precios por fecha (bar plot): permite ver la variación diaria y detectar picos o valles."))
    # Scatter plot: precios vs fechas
    plt.figure(figsize=(8,3))
    plt.scatter(x, y, c=y, cmap='viridis', s=40)
    plt.title(f"Precios vs Fecha - {airline} {dest} {month}")
    plt.ylabel("Precio ($)")
    plt.xlabel("Fecha")
    plt.xticks(rotation=45)
    plt.tight_layout()
    scatter_path = os.path.join(outdir, f"scatter_{airline}_{dest}_{month}.png")
    plt.savefig(scatter_path)
    plt.close()
    imgs.append((scatter_path, "Scatter plot de precios por fecha: útil para ver la dispersión y detectar outliers visualmente."))
    # Boxplot: distribución y outliers
    plt.figure(figsize=(4,3))
    sns.boxplot(y=y, color='lightcoral')
    plt.title(f"Boxplot precios - {airline} {dest} {month}")
    plt.ylabel("Precio ($)")
    plt.tight_layout()
    box_path = os.path.join(outdir, f"box_{airline}_{dest}_{month}.png")
    plt.savefig(box_path)
    plt.close()
    imgs.append((box_path, "Boxplot: muestra la mediana, cuartiles y posibles outliers de los precios."))
    # Heatmap: precios por día del mes (si hay suficientes datos)
    if len(x) > 5:
        days = [d.day for d in x]
        min_day, max_day = min(days), max(days)
        price_map = {d.day: p for d, p in zip(x, y)}
        data = [[price_map.get(day, np.nan) for day in range(min_day, max_day+1)]]
        data = np.array(data, dtype=float)  # Asegura que todo sea numérico
        plt.figure(figsize=(8,1.5))
        sns.heatmap(data, annot=True, fmt=".0f", cmap="YlGnBu", cbar=False, xticklabels=range(min_day, max_day+1), yticklabels=['Precio'], mask=np.isnan(data))
        plt.title(f"Heatmap precios por día - {airline} {dest} {month}")
        plt.tight_layout()
        heatmap_path = os.path.join(outdir, f"heatmap_{airline}_{dest}_{month}.png")
        plt.savefig(heatmap_path)
        plt.close()
        imgs.append((heatmap_path, "Heatmap: visualiza los precios por día del mes, resaltando tendencias y días atípicos."))
    return imgs

def analyze_flight_stats(flight_data, pdf_path="flight_stats.pdf"):
    """
    Recibe un diccionario con los datos de vuelos de ambas aerolíneas y genera un PDF con el análisis y gráficos.
    """
    outdir = "flight_stats_imgs"
    os.makedirs(outdir, exist_ok=True)
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, y, "Análisis Estadístico de Vuelos")
    y -= 0.5 * inch
    c.setFont("Helvetica", 10)
    for airline in ['level', 'aerolineas']:
        c.setFont("Helvetica-Bold", 13)
        c.drawString(inch, y, f"Estadísticas para {airline.capitalize()}")
        y -= 0.3 * inch
        vuelos = flight_data.get(airline, [])
        if not vuelos:
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, "Sin datos para analizar.")
            y -= 0.2 * inch
            continue
        stats = defaultdict(list)
        for v in vuelos:
            dest = v['destination']
            date = v['date']
            price = v['price']
            if not price or not date:
                continue
            month = date[:7]  # 'YYYY-MM'
            stats[(dest, month)].append((date, price))
        for (dest, month), items in stats.items():
            precios = [p for _, p in items]
            fechas = [d for d, _ in items]
            if not precios:
                continue
            avg = mean(precios)
            med = median(precios)
            mn = min(precios)
            mx = max(precios)
            std = stdev(precios) if len(precios) > 1 else 0
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y, f"{airline.capitalize()} {dest} {month}")
            y -= 0.2 * inch
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, f"Promedio: ${avg:.0f}, Mediana: ${med:.0f}, Mínimo: ${mn}, Máximo: ${mx}, Desvío: ${std:.0f}")
            y -= 0.18 * inch
            outliers = [ (d, p) for d, p in items if p < avg - 1.5*std ]
            if outliers:
                c.drawString(inch, y, f"Outliers (precios muy bajos): {outliers}")
                y -= 0.18 * inch
            fechas_ordenadas = sorted(fechas)
            gaps = []
            for i in range(1, len(fechas_ordenadas)):
                prev = datetime.strptime(fechas_ordenadas[i-1], "%Y-%m-%d")
                curr = datetime.strptime(fechas_ordenadas[i], "%Y-%m-%d")
                if (curr - prev).days > 1:
                    gaps.append((fechas_ordenadas[i-1], fechas_ordenadas[i]))
            if gaps:
                c.drawString(inch, y, f"Gaps de fechas con precio: {gaps}")
                y -= 0.18 * inch
            precios_fechas = sorted(items, key=lambda x: x[1])
            mejores = precios_fechas[:3]
            c.drawString(inch, y, f"Mejores fechas alternativas: {mejores}")
            y -= 0.18 * inch
            heatmap_txt = ', '.join(["%s:$%s" % (d[-2:], p) for d, p in sorted(items)])
            c.drawString(inch, y, f"Mapa de calor: {heatmap_txt}")
            y -= 0.18 * inch
            # Gráficos
            imgs = plot_and_save(precios, fechas, dest, month, airline, outdir)
            for img_path, desc in imgs:
                if y < 2*inch:
                    c.showPage()
                    y = height - inch
                c.drawImage(img_path, inch, y-2.2*inch, width=6*inch, height=2*inch, preserveAspectRatio=True)
                y -= 2.2 * inch
                c.setFont("Helvetica-Oblique", 9)
                c.drawString(inch, y, desc)
                y -= 0.25 * inch
                c.setFont("Helvetica", 10)
            y -= 0.08 * inch
            if y < inch:
                c.showPage()
                y = height - inch
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(inch, y, "Este reporte fue generado automáticamente.")
    c.save()

# Descripción de los gráficos:
# - Bar plot: distribución de precios por fecha, útil para ver tendencias y picos.
# - Scatter plot: precios vs fechas, muestra dispersión y outliers.
# - Boxplot: visualiza la mediana, cuartiles y outliers.
# - Heatmap: precios por día del mes, resalta tendencias y días atípicos.

