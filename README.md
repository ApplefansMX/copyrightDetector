# Verificación visual local — baseline experimental

Compara dos videos **locales**, encuentra secuencias perceptualmente similares y
devuelve intervalos, cobertura y razones en JSON. No descarga ni envía archivos,
no usa APIs y no analiza audio. Una coincidencia visual no determina derechos.

## Estado de validación

Implementación inicial, umbrales **EXPERIMENTALES / NO CALIBRADOS**. La suite
unitaria cubre imágenes sintéticas y secuencias en memoria. La suite de integración
genera videos sintéticos temporales y prueba transformaciones reales con FFmpeg,
pero se omite explícitamente si faltan FFmpeg/ffprobe. No confundir esos skips con
una validación del pipeline multimedia. Se necesita material autorizado real para
medir precisión y recall en el dominio del proyecto.

## Dependencias y preparación

- CPython 3.12.14 fue el intérprete utilizado en esta iteración.
- `requirements.txt`: NumPy 2.3.5 y Pillow 12.3.0.
- FFmpeg **y** ffprobe como ejecutables externos en PATH, o rutas explícitas.
- Pruebas con `unittest` de la biblioteca estándar; no hace falta pytest.

No se instaló nada ni se hicieron llamadas externas durante la implementación.
ImageHash requeriría componentes adicionales no disponibles en este entorno;
el baseline calcula directamente un DCT pHash con NumPy/Pillow. No pretende
producir los mismos bits que ImageHash. No se incorporaron SciPy, ML ni GPU.

Para preparar otro entorno, cuando esté autorizado obtener dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
```

En un entorno sin red, usar wheels locales previamente obtenidos:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links C:\wheels -r requirements.txt
```

El comando informa claramente `ToolUnavailable` y termina con código 2 si falta
algún ejecutable. Los informes registran versiones de Python, NumPy, Pillow y
ambos ejecutables. Para reproducir exactamente, conservar además el mismo build
de FFmpeg: no se declara reproducibilidad binaria entre builds diferentes.

## Comandos

Desde la raíz del proyecto:

```powershell
python main.py verify C:\videos\original.mp4 C:\videos\candidate.mp4 --output resultado.json
python main.py verify C:\videos\original.mp4 C:\videos\candidate.mp4 --sample-fps 2 --parameters benchmarks/parameters.baseline.json --output resultado-2fps.json
python main.py verify C:\videos\original.mp4 C:\videos\candidate.mp4 --ffmpeg C:\ffmpeg\bin\ffmpeg.exe --ffprobe C:\ffmpeg\bin\ffprobe.exe
python -m unittest discover -s tests -v
```

En el entorno Codex de esta iteración, `python` no estaba en PATH. El intérprete
disponible se puede invocar así, sustituyendo `python` en los comandos anteriores:

```powershell
$python = 'C:\Users\ceric\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s tests -v
```

Las pruebas de integración permiten rutas explícitas mediante variables:

```powershell
$env:FFMPEG = 'C:\ffmpeg\bin\ffmpeg.exe'
$env:FFPROBE = 'C:\ffmpeg\bin\ffprobe.exe'
python -m unittest tests.test_integration -v
```

`verify` siempre imprime JSON a stdout; los errores operativos se imprimen como
JSON a stderr con código de salida 2. Las cuatro decisiones analíticas terminan
con código 0: no utilizar el exit code como clasificación de coincidencia.
Los archivos de reporte se crean exclusivamente: nunca sobrescribe un resultado
existente, ni siquiera si se pasa por accidente la ruta de un video de entrada.

El experimento de discovery permanece disponible como `python main.py discovery`.
**Ese comando sí usa servicios externos y créditos.** No fue ejecutado en esta
iteración. Ejecutar o importar `main.py` ya no inicia búsquedas implícitamente;
sin subcomando muestra ayuda/error de argumentos. Los providers no se modificaron.

## Arquitectura implementada

`main.py` → `verification/pipeline.py` → `media/probe.py` → `media/frames.py`
→ `fingerprinting/visual.py` → `verification/temporal.py`
→ `verification/decision.py` → `evidence/report.py`.

- `probe`: valida archivo local, stream no adjunto, duración y dimensiones.
- `frames`: autorrotación de FFmpeg, corrección SAR, canvas gris acotado y
  muestreo regular configurable (1 fps por defecto).
- `visual`: pHash DCT 64 bits, frame completo y región central al 85%; filtrado
  de poca desviación/entropía y repeticiones consecutivas. Los bordes negros se
  recortan conservadoramente antes de calcular el descriptor.
- `temporal`: distancia Hamming mínima entre vistas, descarte de ambigüedad,
  tracks monotónicos con offset local consistente y separación ante cortes.
- `pipeline`: refinamiento opcional a 4 fps cerca de segmentos detectados.
  Refinamiento no recupera regiones sin ninguna semilla a 1 fps.
- `decision`: duración compartida y cobertura, sin score probabilístico.
- `report`: JSON con timestamps, offsets, distancias, parámetros y versiones.

El protocolo `Descriptor` permite sustituir la firma y distancia, pero cambiar
de algoritmo exige nuevas escalas/umbrales, tests y calibración. La supresión de
repeticiones actual supone firmas binarias; no es una abstracción para cualquier
embedding. No hay plugins externos, colas, base de datos ni servicio web.

Los límites temporales son **aproximados** respecto al inicio decodificado. Se
usan los extremos observados, no se extrapola un segundo extra. Por eso incluso
una copia idéntica puede reportar cobertura inferior al 100%. Cada segmento
indica intervalo de muestreo e incertidumbre de borde. La cobertura global usa
unión de intervalos, evitando doble conteo. El refinamiento puede mantener los
extremos gruesos cuando no hay suficiente evidencia densa o excede un límite.

Los checksums SHA-256 sirven para integridad/reproducibilidad; **no deciden** el
match. No hay fecha variable ni tiempo de ejecución dentro del reporte de
verificación, de modo que un mismo archivo/configuración/runtime produce un
reporte estable. El benchmark sí registra duración de procesamiento.

## Decisiones

| Estado | Interpretación |
|---|---|
| `probable_match` | Secuencias coherentes superan duración y cobertura experimentales |
| `review` | Segmento breve/parcial o motivos ambiguos; posible intro/outro compartido |
| `no_match` | No se encontró secuencia que supere el baseline; no prueba ausencia |
| `insufficient_evidence` | Insuficientes frames informativos no repetidos |

Para `probable_match`, por defecto se requieren al menos 8 segundos compartidos
y 60% de cobertura de **al menos uno** de los videos; esto permite fragmentos de
un original largo. Cada segmento requiere al menos 4 correspondencias y 3 segundos.
Una intro suficientemente larga puede todavía pasar esos umbrales: no existe un
catálogo de intros conocidas ni una garantía contra ese falso positivo.

## Parámetros para calibrar

Todos se pueden modificar en JSON con `--parameters`. Se rechazan parámetros
desconocidos, tipos incompatibles, valores no finitos y límites inválidos.
`--sample-fps` tiene prioridad sobre el JSON.

| Parámetro | Baseline | Papel |
|---|---:|---|
| `sample_fps` | 1 | Muestreo inicial |
| `refine_fps`, `refine` | 4, true | Muestreo denso local |
| `max_hamming` | 10 de 64 bits | Máxima distancia de recuperación |
| `ambiguity_margin`, `max_alternatives` | 2, 3 | Descartar motivos con demasiados empates |
| `min_std`, `min_entropy` | 12, 3 | Descartar frames poco informativos |
| `repeat_hamming` | 2 | Suprimir repetición consecutiva |
| `offset_tolerance` | 0.65 s | Residuo temporal permitido |
| `max_gap_seconds` | 2.5 s | Hueco máximo entre observaciones |
| `min_matches`, `min_segment_seconds` | 4, 3 s | Evidencia mínima de segmento |
| `probable_seconds`, `probable_coverage` | 8 s, 0.6 | Promoción a probable |

Los límites operativos también son configurables: `frame_size=160`,
`max_duration=7200`, `max_frames=8000`, `max_pair_comparisons=20000000`,
`timeout_seconds=180` por subproceso. A 160×160 y 8000 frames el buffer gris puede
ocupar unos 205 MB por extracción; no es un sistema de streaming ilimitado.

No ajustar todos los parámetros contra un único video y presentar el resultado
como precisión general. Separar calibration/evaluation **por original**, congelar
parámetros y evaluar negativos difíciles independientes.

## Benchmark local

No se incluye material audiovisual real. Usar `.local-data/` (ignorado por Git)
o una carpeta externa. Los reportes contienen rutas y hashes: también pueden
ser sensibles. `.gitignore` evita muchos archivos multimedia comunes, pero no
reemplaza una revisión de lo que se añade a control de versiones.

```powershell
python -m benchmarks.generate C:\videos\original.mp4 .local-data\bench-original --negative C:\videos\different.mp4
python -m benchmarks.run .local-data\bench-original\manifest.json --parameters benchmarks\parameters.baseline.json --output .local-data\evaluation.json
```

Ambos aceptan `--ffmpeg` y `--ffprobe`. La generación requiere un original de al
menos 20 segundos y **una carpeta nueva**; no borra ni reemplaza datos existentes.
Ante fallo quedan los archivos ya generados para inspección. Elegir otra carpeta
para repetir. No hay ejecución de comandos leídos del manifiesto.

Genera 12 positivos: identidad, recompresión, resolución, codec FFV1, recorte
inicial, final, medio, overlay, aspecto estirado, crop espacial al 90%, combinación
y corte interno. La reencodificación base usa el encoder MPEG-4 de FFmpeg. Los
derivados se crean sin audio, porque el algoritmo de esta fase es visual.
Los negativos se referencian mediante `--negative` repetible, sin copiarlos.

El manifiesto incluye transformaciones, hashes, etiquetas e intervalos esperados.
El campo `split` comienza como `UNASSIGNED`: asignar `calibration` o `evaluation`
según el original utilizado. Para material con intros compartidas, no etiquetar
todo el caso como ausencia absoluta de material compartido: documentar segmentos
reales y revisar los resultados por caso. Los negativos completamente distintos
usan `expected_segments: []`.

El evaluador conserva errores y reportes por caso. Mide precisión/recall de
`probable_match`, falsos positivos, detección de segmentos en positivos, revisión,
insuficiencia, errores, tiempo e IoU de intervalos en ambos ejes. Los errores no
se eliminan del denominador de recall; `review` no cuenta como positivo automático.
La IoU no valida por sí sola el offset o el emparejamiento de dos segmentos.
Con cero negativos, la tasa de falsos positivos es `null`, no cero. Una precisión
alta con un corpus sin negativos no demuestra discriminación real.

## Limitaciones y primera evaluación real

- No se ha calibrado en personas, escenarios, vestuario o material sensible.
- No analiza música/audio; igualdad de audio no contribuye a la decisión.
- No garantiza crops fuertes, overlays grandes, cambios de velocidad, reversa,
  montajes complejos, videos muy cortos ni similitudes de frames poco distintivos.
- El descarte de repeticiones puede perder escenas estáticas o movimiento lento.
- La recuperación es exhaustiva por par local con límite explícito; no sirve
  como índice de millones de firmas. La agrupación es heurística, no un alineador
  óptimo ni tolerancia general a cualquier edición.
- No incluye detección de cambios de escena todavía: el muestreo uniforme y el
  refinamiento local constituyen el primer baseline medible.
- El parser solo admite contenedores audiovisuales explícitos; no HLS, playlists,
  URLs ni recursos remotos. Los subprocesos tienen timeout y no usan shell.
  No es un sandbox de seguridad completo para decodificadores vulnerables.

Para la primera evaluación proporcionar, **fuera del repositorio**, varios
originales autorizados de 20–120 segundos con movimiento y escenas variadas,
otro video realmente distinto, videos de la misma persona/escenario/vestuario,
pares con música compartida y pares con intro/outro compartido con sus intervalos
anotados. Idealmente usar al menos varios originales para calibración y otros
independientes para evaluación. No hace falta subir material a ningún servicio.
