from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db_connec
from app import models
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

app = FastAPI()

# Ruta para obtener los datos dependiendo del identificador
@app.get("/start_stop/{identificador}")
def get_start_stop_by_identificador(identificador: str, db: Session = Depends(get_db_connec)):
    # Consultar datos de StartStop unidos con DatosMedicionPrincipal
    result = db.query(
        models.StartStop.scan_start,
        models.StartStop.scan_stop,
        models.StartStop.step_start,
        models.StartStop.step_stop,
        models.StartStop.point_scan,
        models.StartStop.point_step
    ).join(
        models.DatosMedicionPrincipal
    ).filter(
        models.DatosMedicionPrincipal.identificador == identificador
    ).all()

    if not result:
        raise HTTPException(status_code=404, detail="Datos no encontrados para el identificador")

    # Consultar datos de PuntosMedicion relacionados con Mediciones
    puntos_medicion_data = db.query(
        models.PuntosMedicion.amplitud4,
        models.PuntosMedicion.rinc,
        models.PuntosMedicion.scan
    ).join(
        models.Mediciones, models.PuntosMedicion.id_medicion == models.Mediciones.id_medicion
    ).filter(
        models.Mediciones.identificador == identificador
    ).order_by(
        models.PuntosMedicion.amplitud4.desc()
    ).all()

    # Extraer datos de `result` para los límites
    scan_start = result[0].scan_start
    scan_stop = result[0].scan_stop
    step_start = result[0].step_start
    step_stop = result[0].step_stop
    point_scan = int(result[0].point_scan)  # Asegurarse de que sea entero
    point_step = int(result[0].point_step)  # Asegurarse de que sea entero

    # Procesar datos de PuntosMedicion
    radiation_df = pd.DataFrame(
        [{"Rinc": p.rinc, "Scan": p.scan, "Bin4Amptd": p.amplitud4} for p in puntos_medicion_data]
    )

    # Limitar amplitud
    radiation_df["Bin4Amptd"] = np.where(radiation_df["Bin4Amptd"] > -10, radiation_df["Bin4Amptd"], -10)

    # Crear DataFrame 3D
    radiation3d = pd.DataFrame()
    
    for i in range(point_scan):  
        scan_data = radiation_df[radiation_df["Scan"] == i].set_index("Rinc")
        radiation3d[i] = scan_data["Bin4Amptd"]

    # Ejes
    x = np.linspace(scan_start, scan_stop, point_scan)  # Eje X
    y = np.linspace(step_start, step_stop, point_step)  # Eje Y

    # Crear subgráficas
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Gráfico 3D", "Gráfico Azimut", "Gráfico Elevación"),
        specs=[[{'type': 'surface'}, {'type': 'xy'}, {'type': 'xy'}]]
    )

    # Gráfica 3D
    fig.add_trace(
        go.Surface(z=radiation3d.values, x=x, y=y, colorscale='Jet'),
        row=1, col=1
    )

    # Gráfica Azimut
    plano = radiation3d.shape[1] // 2
    fig.add_trace(
        go.Scatter(x=x, y=radiation3d[plano], mode='lines', name='Azimut'),
        row=1, col=2
    )

    # Gráfica Elevación
    elevacion = radiation3d.T
    fig.add_trace(
        go.Scatter(x=y, y=elevacion[plano], mode='lines', name='Elevación'),
        row=1, col=3
    )

    # Configurar diseño
    fig.update_layout(
        title="Gráficas de Radiación",
        height=600,
        template="plotly_white"
    )

    # Mostrar gráficas
    fig.show()

  