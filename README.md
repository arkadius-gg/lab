# lab

Plataforma Kubernetes casera (k3s en dos VMs) gestionada con Flux desde este repo. Incluye
Prometheus, Grafana, Loki, Tempo y OpenTelemetry, alertas a Telegram y un servicio plantilla,
`hola`, que se despliega con un push.

## Estructura

- `cluster/`: lo que Flux aplica al cluster.
  - `flux-system/`, `plataforma.yaml`, `servicios.yaml`, `cluster-vars.yaml`: Flux y variables.
  - `plataforma/`: Traefik (Gateway API), monitorización, logs y trazas, alertas y secretos
    cifrados con SOPS (`.sops.yaml`).
  - `servicios/<nombre>/`: un servicio por carpeta (Namespace, Deployment, Service, HTTPRoute).
- `apps/<nombre>/`: el código y el `Dockerfile` de cada servicio.
- `.github/workflows/`: el CI construye cada imagen cambiada, la publica en GHCR y escribe la
  etiqueta en `cluster/servicios/<nombre>/kustomization.yaml`.

## Servicio nuevo

1. Copiar `apps/hola` a `apps/<nombre>` y `cluster/servicios/hola` a `cluster/servicios/<nombre>`;
   cambiar el nombre en los manifiestos y en `images:` del `kustomization.yaml`.
2. Push. El CI construye la imagen y Flux la despliega en `<nombre>.<dominio_base>`.
3. La primera vez, comprobar que el paquete de GHCR es público (aquí heredó la visibilidad
   del repo); si no, el pod queda en `ImagePullBackOff`.

El Deployment de `hola` es la plantilla: 2 réplicas, `readinessProbe` y `livenessProbe`,
`preStop` de 5 s (Traefik tarda ~2 s en retirar un pod; sin esa espera salen 502 al borrarlo)
y `securityContext` restringido.

## Regla de la plataforma: x86-64-v2

La CPU de las VMs no tiene AVX. Una imagen compilada para x86-64-v3 (UBI/RHEL 10, algunas
bases de datos y runtimes de IA) muere con `illegal instruction`. Usar bases Debian/Ubuntu o
binarios Go estándar.
