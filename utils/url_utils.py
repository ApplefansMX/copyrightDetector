from urllib.parse import urlparse

def normalize_url(url):
    parsed = urlparse(url)

    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    path = parsed.path.rstrip("/")

    return f"{domain}{path}"

def is_authorized_url(url, authorized_profiles):
    parsed_url = urlparse(url)

    domain = parsed_url.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    path_parts = [
        part
        for part in parsed_url.path.split("/")
        if part
    ]

    for profile in authorized_profiles:
        parsed_profile = urlparse(profile["url"])

        profile_domain = parsed_profile.netloc.lower()

        if profile_domain.startswith("www."):
            profile_domain = profile_domain[4:]

        profile_parts = [
            part
            for part in parsed_profile.path.split("/")
            if part
        ]

        # El dominio debe coincidir
        if domain != profile_domain:
            continue

        # El perfil debe existir
        if not profile_parts:
            continue

        username = profile_parts[0].lower()

        # El primer segmento de la URL debe ser el usuario autorizado
        if path_parts and path_parts[0].lower() == username:
            return True

    return False

def get_platform(url):
    parsed = urlparse(url)

    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    domain_parts = domain.split(".")

    if len(domain_parts) >= 2:
        return domain_parts[-2]

    return domain