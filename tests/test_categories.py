from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from tests import BaseTestCase
from app import db
from app.models import Category


class CategoryTests(BaseTestCase):
    def create_category(self, name="Hrana", color="#FF8800"):
        response = self.client.post(
            "/categories", json={"name": name, "color": color}
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_create_category_trims_name_and_preserves_color(self):
        category = self.create_category("  Hrana  ", "#aBc123")

        self.assertIsInstance(category["id"], int)
        self.assertEqual(category["name"], "Hrana")
        self.assertEqual(category["color"], "#aBc123")
        stored = db.session.get(Category, category["id"])
        self.assertEqual(stored.name, "Hrana")

    def test_create_category_accepts_boundary_name_lengths(self):
        for name in ("A", "B" * 30):
            with self.subTest(length=len(name)):
                category = self.create_category(name)
                self.assertEqual(category["name"], name)

    def test_create_category_requires_both_fields(self):
        for data in ({}, {"name": "Hrana"}, {"color": "#123456"}):
            with self.subTest(data=data):
                response = self.client.post("/categories", json=data)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 0)

    def test_create_and_update_reject_invalid_json(self):
        category = self.create_category()
        routes = (("POST", "/categories"),
                  ("PUT", f"/categories/{category['id']}"))

        for method, url in routes:
            for body in ("null", "[]", '"tekst"', "123", "true", "{", ""):
                with self.subTest(method=method, body=body):
                    response = self.client.open(
                        url, method=method, data=body,
                        content_type="application/json"
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

            with self.subTest(method=method, content_type="text/plain"):
                response = self.client.open(
                    url, method=method,
                    data='{"name": "Prevoz", "color": "#123456"}',
                    content_type="text/plain"
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)

    def test_create_and_update_reject_invalid_names(self):
        category = self.create_category()
        routes = (("POST", "/categories"),
                  ("PUT", f"/categories/{category['id']}"))

        for method, url in routes:
            for name in (
                None, True, 123, "", " \t\n", "A" * 31,
                "Hrana\x00", "Hrana\ud800", "Hrana\udfff",
            ):
                with self.subTest(method=method, name=name):
                    response = self.client.open(
                        url, method=method,
                        json={"name": name, "color": "#123456"}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)
        self.assertEqual(db.session.get(Category, category["id"]).name, "Hrana")

    def test_create_and_update_reject_invalid_colors(self):
        category = self.create_category()
        routes = (("POST", "/categories"),
                  ("PUT", f"/categories/{category['id']}"))
        colors = (None, True, 123, "", "red", "123456", "#123",
                  "#1234567", "#GG0000", " #123456", "#123456\n")

        for method, url in routes:
            for color in colors:
                with self.subTest(method=method, color=color):
                    response = self.client.open(
                        url, method=method,
                        json={"name": "Prevoz", "color": color}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)
        self.assertEqual(db.session.get(Category, category["id"]).color, "#FF8800")

    def test_list_categories_returns_empty_list(self):
        response = self.client.get("/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_list_categories_orders_by_name(self):
        prevoz = self.create_category("Prevoz")
        hrana = self.create_category("Hrana")

        response = self.client.get("/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [hrana, prevoz])

    def test_create_category_rejects_case_insensitive_duplicates(self):
        self.create_category()

        for name in ("Hrana", "hrana", "HRANA", " HrAnA "):
            with self.subTest(name=name):
                response = self.client.post(
                    "/categories", json={"name": name, "color": "#123456"}
                )
                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.get_json(), {"error": "Category already exists"}
                )

        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)

    def test_update_category_changes_both_fields(self):
        category = self.create_category()

        response = self.client.put(
            f"/categories/{category['id']}",
            json={"name": "  Namirnice  ", "color": "#00AAff"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "id": category["id"], "name": "Namirnice", "color": "#00AAff"
        })
        stored = db.session.get(Category, category["id"])
        self.assertEqual(stored.name, "Namirnice")
        self.assertEqual(stored.color, "#00AAff")

    def test_update_category_keeps_omitted_fields(self):
        category = self.create_category()
        url = f"/categories/{category['id']}"

        response = self.client.put(url, json={"color": "#123456"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], "Hrana")

        response = self.client.put(url, json={"name": "Namirnice"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["color"], "#123456")

    def test_update_category_accepts_its_own_name(self):
        category = self.create_category()

        response = self.client.put(
            f"/categories/{category['id']}", json={"name": "  HRANA  "}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], "HRANA")
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)

    def test_update_category_rejects_another_category_name(self):
        self.create_category("Hrana")
        prevoz = self.create_category("Prevoz")

        response = self.client.put(
            f"/categories/{prevoz['id']}",
            json={"name": "  hRaNa  ", "color": "#123456"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(), {"error": "Category already exists"}
        )
        stored = db.session.get(Category, prevoz["id"])
        self.assertEqual(stored.name, "Prevoz")
        self.assertEqual(stored.color, prevoz["color"])

    def test_update_and_delete_missing_category_return_404(self):
        for category_id in (0, 999, 2147483648, 10 ** 100):
            for method in ("PUT", "DELETE"):
                with self.subTest(method=method, category_id=category_id):
                    response = self.client.open(
                        f"/categories/{category_id}", method=method,
                        json={"name": "Hrana", "color": "#123456"}
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(
                        response.get_json(), {"error": "Category not found"}
                    )

    def test_delete_category_removes_only_requested_category(self):
        hrana = self.create_category("Hrana")
        prevoz = self.create_category("Prevoz")

        response = self.client.delete(f"/categories/{hrana['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertIsNone(db.session.get(Category, hrana["id"]))
        self.assertEqual(self.client.get("/categories").get_json(), [prevoz])

    def test_database_rejects_case_insensitive_duplicate_insert(self):
        self.create_category("Hrana")
        db.session.add(Category(name="HRANA", color="#123456"))

        with self.assertRaises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 1)

    def test_database_rejects_case_insensitive_duplicate_update(self):
        self.create_category("Hrana")
        prevoz = self.create_category("Prevoz")
        stored = db.session.get(Category, prevoz["id"])
        stored.name = "hrana"

        with self.assertRaises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        self.assertEqual(stored.name, "Prevoz")
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 2)

    def test_create_conflict_after_precheck_returns_409_and_rolls_back(self):
        original = self.create_category("Hrana")

        # Početna provera propusti duplikat, ali stvarni upis radi baza.
        with patch.object(db.session, "execute") as execute:
            execute.return_value.scalar_one_or_none.return_value = None
            response = self.client.post(
                "/categories", json={"name": "HRANA", "color": "#123456"}
            )
            execute.assert_called_once()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(), {"error": "Category already exists"}
        )
        self.assertEqual(self.client.get("/categories").get_json(), [original])

        # Sledeći upis uspeva samo ako je neuspešna transakcija poništena.
        self.create_category("Prevoz")
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 2)

    def test_update_conflict_after_precheck_returns_409_and_rolls_back(self):
        hrana = self.create_category("Hrana")
        prevoz = self.create_category("Prevoz")

        with patch.object(db.session, "execute") as execute:
            execute.return_value.scalar_one_or_none.return_value = None
            response = self.client.put(
                f"/categories/{prevoz['id']}",
                json={"name": "hRaNa", "color": "#123456"}
            )
            execute.assert_called_once()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(), {"error": "Category already exists"}
        )
        self.assertEqual(
            self.client.get("/categories").get_json(), [hrana, prevoz]
        )

        self.create_category("Stan")
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Category)), 3)
