# Deploying PyFarm

Deployment — Docker images, Raspberry Pi imaging, systemd units and over-the-air
updates — now lives in its own repository:

➡️ **[pyfarm-deploy](https://github.com/CitizenWeather/pyfarm-deploy)**

See [`pyfarm-deploy/DEPLOYMENT.md`](https://github.com/CitizenWeather/pyfarm-deploy/blob/main/DEPLOYMENT.md)
for the full guide.

## TL;DR

```bash
git clone https://github.com/CitizenWeather/pyfarm-deploy
cd pyfarm-deploy
sudo bash scripts/setup.sh          # Raspberry Pi bare metal
# or
docker compose up -d                # Docker
```

For the sensor/actuator API used in a GrowSpec, see [EXTENSIONS.md](EXTENSIONS.md).
