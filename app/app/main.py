from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db_connec
from app import models
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import plotly
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import plotly.graph_objects as go
import plotly.offline as pyo
import numpy as np

app = FastAPI()

# Montar la carpeta estática
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

templates = Jinja2Templates(directory="app/templates")  # Ruta de las plantillas

# Ruta para obtener los datos dependiendo del identificador y mostrar los gráficos
@app.get("/start_stop/{identificador}")
def get_start_stop_by_identificador(identificador: str, db: Session = Depends(get_db_connec), request: Request = None):
    # Consultar datos de StartStop
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

    # Consultar datos de PuntosMedicion
    puntos_medicion_data = db.query(
        models.PuntosMedicion.scan,
        models.PuntosMedicion.rinc,
        models.PuntosMedicion.amplitud4
    ).join(
        models.Mediciones, models.PuntosMedicion.id_medicion == models.Mediciones.id_medicion
    ).filter(
        models.Mediciones.identificador == identificador  # Filtrado por identificador
    ).all()

    # Extraer los valores de los datos de PuntosMedicion
    amplitud4_values = [p.amplitud4 for p in puntos_medicion_data]
    rinc_values = [p.rinc for p in puntos_medicion_data]
    scan_values = [p.scan for p in puntos_medicion_data]

    # Extraer datos de `result` para los límites
    scan_start = result[0].scan_start
    scan_stop = result[0].scan_stop
    step_start = result[0].step_start
    step_stop = result[0].step_stop
    point_scan = int(result[0].point_scan)  # Asegurarse de que sea entero
    point_step = int(result[0].point_step)  # Asegurarse de que sea entero

    radiation_df = pd.DataFrame(
        {"Bin4Amptd": amplitud4_values, "Rinc": rinc_values, "Scan": scan_values}
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
    fig1 = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Patrón de Radiacíon", "Perfil Azimut", "Perfil Elevación"),
        specs=[[{'type': 'surface'}, {'type': 'scatter'}, {'type': 'scatter'}]]
    )

    # Gráfico 3D (fig1)
    fig1.add_trace(
        go.Surface(
            z=radiation3d.values, 
            x=x, 
            y=y, 
            colorscale='Viridis',  # Esquema de colores mejorado
            colorbar=dict(title="", tickvals=[-40, -30, -20,-10, 0, 10, 20, 30, 40], ticktext=["-40", "-30", "-20","-10", "0", "10", "20", "30", "40"]),
            contours=dict(
                z=dict(show=True, usecolormap=True, highlightcolor="yellow", project_z=True)
            )
        ),
        row=1, col=1
    )

    # Títulos y etiquetas para el gráfico 3D
    fig1.update_layout(
        title="",
        scene=dict(
            xaxis_title="Scan (m)",
            yaxis_title="Step (m)",
            zaxis_title="Amplitud Bin4"
        ),
        template="plotly_dark",
    )

    # Gráfico Azimut
    plano = radiation3d.shape[1] // 2
    fig1.add_trace(
        go.Scatter(
            x=x, 
            y=radiation3d[plano], 
            mode='lines', 
            name='Azimut', 
            line=dict(color='royalblue', width=3)
        ),
        row=1, col=2
    )

    # Títulos y formato del gráfico Azimut
    fig1.update_xaxes(title_text="Scan (m)", row=1, col=2)
    fig1.update_yaxes(title_text="Amplitud Bin4", row=1, col=2)

    # Gráfico Elevación
    elevacion = radiation3d.T
    fig1.add_trace(
        go.Scatter(
            x=y, 
            y=elevacion[plano], 
            mode='lines', 
            name='Elevación', 
            line=dict(color='darkorange', width=3)
        ),
        row=1, col=3
    )

    # Títulos y formato del gráfico Elevación
    fig1.update_xaxes(title_text="Step (m)", row=1, col=3)
    fig1.update_yaxes(title_text="", row=1, col=3)

    # Crear otro gráfico 3D (fig2) con diferentes configuraciones
    fig2 = go.Figure(data=[go.Surface(z=radiation3d.values, x=x, y=y, colorscale='Viridis')])

    # Títulos y diseño para el segundo gráfico 3D
    fig2.update_layout(
        title="Patrón de Radisción",
        scene=dict(
            xaxis_title="Scan (m)",
            yaxis_title="Step (m)",
        ),
        template="plotly_dark",
    )

    # Convertir los gráficos a HTML
    graph_html1 = plotly.offline.plot(fig1, auto_open=False, output_type="div")
    
    return templates.TemplateResponse(
    "index.html",
    {
        "request": request,
        "x_values": x.tolist(),
        "y_values": y.tolist(),
        "z_values": radiation3d.values.tolist(),
        "graph_html1": graph_html1,
    }
)

