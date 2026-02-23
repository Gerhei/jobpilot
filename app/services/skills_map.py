SKILLS_MAP: dict[str, str] = {
    # Python
    "питон": "python",
    "python3": "python",
    "python 3": "python",
    "py": "python",
    # FastAPI
    "fast api": "fastapi",
    "fast_api": "fastapi",
    # PostgreSQL
    "postgres": "postgresql",
    "psql": "postgresql",
    "pg": "postgresql",
    "postgresql 16": "postgresql",
    # Redis
    "redis cache": "redis",
    # Docker
    "docker compose": "docker",
    "docker-compose": "docker",
    # Celery
    "celery beat": "celery",
    "celery worker": "celery",
    # SQLAlchemy
    "sqlalchemy 2": "sqlalchemy",
    "sa": "sqlalchemy",
    # Alembic
    "db migrations": "alembic",
    # RabbitMQ
    "rabbit": "rabbitmq",
    "rabbit mq": "rabbitmq",
    "amqp": "rabbitmq",
    # Kubernetes
    "к8с": "kubernetes",
    "k8s": "kubernetes",
    "кубернетес": "kubernetes",
    # Kafka
    "apache kafka": "kafka",
    # Django
    "django rest": "django",
    "drf": "django",
    # asyncio
    "async": "asyncio",
    "asyncio python": "asyncio",
    # pytest
    "pytest-asyncio": "pytest",
    # git
    "gitlab": "git",
    "github": "git",
    # Linux
    "ubuntu": "linux",
    "debian": "linux",
    # AWS
    "amazon web services": "aws",
    "amazon s3": "aws",
    "ec2": "aws",
}


def normalize_skill(raw: str) -> str:
    key = raw.strip().lower()
    return SKILLS_MAP.get(key, key)
