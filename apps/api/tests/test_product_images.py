"""A vendor uploads a picture for a product instead of pasting an address."""

import base64

from conftest import Env
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_catalog_management import bola_headers, make_product

from app.models import ProductImage

PNG = b"\x89PNG\r\n\x1a\n" + b"not really a picture, but it starts like one"
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-ish bytes"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def upload(client: TestClient, data: bytes = PNG, **kwargs: object):
    return client.post("/product-images", json={"data": b64(data)}, **kwargs)


def picture_count(env: Env) -> int:
    with env.session() as session:
        return session.scalar(select(func.count()).select_from(ProductImage)) or 0


def test_uploading_needs_a_signed_in_vendor(anonymous_client: TestClient) -> None:
    assert upload(anonymous_client).status_code == 401


def test_an_uploaded_picture_becomes_a_products_picture_and_anyone_can_see_it(
    client: TestClient, anonymous_client: TestClient
) -> None:
    response = upload(client)
    assert response.status_code == 201
    image_url = response.json()["imageUrl"]
    assert image_url.startswith("/product-images/")

    product = make_product(client, imageUrl=image_url)
    assert product["imageUrl"] == image_url

    seen = anonymous_client.get(image_url)  # buyers' browsers fetch it with no sign-in
    assert seen.status_code == 200
    assert seen.content == PNG
    assert seen.headers["content-type"] == "image/png"
    assert "immutable" in seen.headers["cache-control"]
    assert seen.headers["x-content-type-options"] == "nosniff"


def test_the_type_comes_from_the_bytes_not_from_the_upload(client: TestClient) -> None:
    image_url = upload(client, JPEG).json()["imageUrl"]
    assert client.get(image_url).headers["content-type"] == "image/jpeg"


def test_only_real_pictures_are_accepted(client: TestClient) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    for data in (b"plain text", svg, b"%PDF-1.7 ...", b""):
        assert upload(client, data).status_code == 400, data
    assert client.post("/product-images", json={"data": "!!! not base64 !!!"}).status_code == 400
    assert client.post("/product-images", json={}).status_code == 400


def test_a_huge_picture_is_refused(client: TestClient) -> None:
    assert upload(client, PNG + b"0" * 1_600_000).status_code == 400


def test_a_missing_or_odd_picture_id_is_a_404(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/product-images/nope").status_code == 404
    assert anonymous_client.get("/product-images/00000000-0000-0000-0000-000000000000").status_code == 404


def test_a_product_cannot_use_another_vendors_picture(env: Env, client: TestClient) -> None:
    bola_image = upload(client, PNG, headers=bola_headers(env)).json()["imageUrl"]

    attempt = client.post(
        "/products",
        json={
            "sku": "tote-02",
            "name": "Tote",
            "basePriceKobo": 3_000_000,
            "floorPriceKobo": 2_600_000,
            "imageUrl": bola_image,
        },
    )
    assert attempt.status_code == 400

    own = make_product(client)
    assert client.patch(f"/products/{own['id']}", json={"imageUrl": bola_image}).status_code == 400


def test_an_old_web_address_still_works(client: TestClient) -> None:
    product = make_product(client, imageUrl="https://example.com/tote.jpg")
    assert product["imageUrl"] == "https://example.com/tote.jpg"
    assert client.patch(f"/products/{product['id']}", json={"imageUrl": "javascript:alert(1)"}).status_code == 400


def test_replacing_a_picture_forgets_the_old_one(env: Env, client: TestClient) -> None:
    first = upload(client, PNG).json()["imageUrl"]
    second = upload(client, JPEG).json()["imageUrl"]
    product = make_product(client, imageUrl=first)
    before = picture_count(env)

    updated = client.patch(f"/products/{product['id']}", json={"imageUrl": second})
    assert updated.json()["product"]["imageUrl"] == second
    assert picture_count(env) == before - 1
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200


def test_removing_a_product_forgets_its_picture(env: Env, client: TestClient) -> None:
    image_url = upload(client).json()["imageUrl"]
    product = make_product(client, imageUrl=image_url)

    assert client.delete(f"/products/{product['id']}").json() == {"deleted": True, "archived": False}
    assert client.get(image_url).status_code == 404


def test_a_picture_two_products_share_is_kept_until_both_let_go(client: TestClient) -> None:
    image_url = upload(client).json()["imageUrl"]
    one = make_product(client, sku="tote-a", imageUrl=image_url)
    two = make_product(client, sku="tote-b", imageUrl=image_url)

    client.delete(f"/products/{one['id']}")
    assert client.get(image_url).status_code == 200
    client.patch(f"/products/{two['id']}", json={"imageUrl": ""})
    assert client.get(image_url).status_code == 404
