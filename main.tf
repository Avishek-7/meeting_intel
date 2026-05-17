# main.tf
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# ── Network ──────────────────────────────────────────────
resource "docker_network" "meeting_intel" {
  name = "meeting_intel_network"
}

# ── Volumes ───────────────────────────────────────────────
resource "docker_volume" "postgres_data" {
  name = "meeting_intel_postgres_data"
}

resource "docker_volume" "redis_data" {
  name = "meeting_intel_redis_data"
}

# ── Images ────────────────────────────────────────────────
resource "docker_image" "postgres" {
  name         = "postgres:16-alpine"
  keep_locally = true
}

resource "docker_image" "redis" {
  name         = "redis:7-alpine"
  keep_locally = true
}

# ── PostgreSQL ────────────────────────────────────────────
resource "docker_container" "db" {
  name    = "meeting_intel_db"
  image   = docker_image.postgres.image_id
  restart = "unless-stopped"

  env = [
    "POSTGRES_USER=${var.db_user}",
    "POSTGRES_PASSWORD=${var.db_password}",
    "POSTGRES_DB=${var.db_name}",
  ]

  volumes {
    volume_name    = docker_volume.postgres_data.name
    container_path = "/var/lib/postgresql/data"
  }

  ports {
    internal = 5432
    external = 5432
  }

  networks_advanced {
    name = docker_network.meeting_intel.name
  }

  healthcheck {
    test         = ["CMD-SHELL", "pg_isready -U ${var.db_user}"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 5
    start_period = "10s"
  }
}

# ── Redis ─────────────────────────────────────────────────
resource "docker_container" "redis" {
  name    = "meeting_intel_redis"
  image   = docker_image.redis.image_id
  command = ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
  restart = "unless-stopped"

  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }

  ports {
    internal = 6379
    external = 6379
  }

  networks_advanced {
    name = docker_network.meeting_intel.name
  }

  healthcheck {
    test     = ["CMD", "redis-cli", "ping"]
    interval = "10s"
    timeout  = "5s"
    retries  = 5
  }
}

# ── API ───────────────────────────────────────────────────
resource "docker_image" "api" {
  name = "meeting_intel_api"
  build {
    context    = path.module
    dockerfile = "Dockerfile"
  }
  triggers = {
    dockerfile = filemd5("${path.module}/Dockerfile")
  }
}

resource "docker_container" "api" {
  name    = "meeting_intel_api"
  image   = docker_image.api.image_id
  restart = "unless-stopped"

  env_file = ".env"

  ports {
    internal = 8000
    external = 8000
  }

  networks_advanced {
    name = docker_network.meeting_intel.name
  }

  depends_on = [docker_container.db, docker_container.redis]
}

# ── Worker ────────────────────────────────────────────────
resource "docker_container" "worker" {
  name    = "meeting_intel_worker"
  image   = docker_image.api.image_id
  command = ["rq", "worker", "--url", "redis://meeting_intel_redis:6379/0", "default"]
  restart = "unless-stopped"

  env_file = ".env"

  env = [
    "PYTHONPATH=/app/backend"
  ]

  networks_advanced {
    name = docker_network.meeting_intel.name
  }

  depends_on = [docker_container.db, docker_container.redis]
}
