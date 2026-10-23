# Two Level Capital dApp 
Aquí contiene los archivos de la version de la dApp (0.2) con submisión de cambios hasta 30 octubre 2026


![Texto alternativo](url-de-la-imagen)


# build_tools — del prototipo (.jsx) a la página publicada (.html)

El `.jsx` es la fuente de verdad. Pasos:

1. `python3 build_html.py ../dashia_app_prototype.jsx icons_and_chart.jsx ../dashia_app.html ../dashia_app.html`
   (reemplaza imports, storage, llamada a la IA, descarga y gráficos por sus equivalentes publicables;
   cada reemplazo verifica que el texto exista y falla en voz alta si el .jsx cambió de forma).
2. Verificar ANTES de publicar (esbuild solo valida sintaxis; en esta sesión una edición rompió la app y la
   sintaxis seguía pasando): extraer el script del HTML, transformarlo con
   `esbuild --loader=jsx --jsx=transform` y correr `node smoke_test.js`, que ejecuta cada pantalla con un
   React de mentira y revisa que las traducciones coincidan en ES/EN.
3. Publicar actualizando la misma URL.

Límite del smoke test: ejecuta el render inicial, NO los efectos (carga de sesión, voz, llamadas a la IA) ni
clics reales. Eso solo se confirma abriendo la página.
