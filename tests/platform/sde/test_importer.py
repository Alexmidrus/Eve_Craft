from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.platform.sde.domain.models import SdeRemoteVersion
from eve_craft.platform.sde.infrastructure.importer import SdeImporter


def _jsonl_bytes(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def build_sample_sde_archive(
    target_path: Path,
    build_number: int = 999001,
    include_orphan_blueprint_refs: bool = False,
    include_duplicate_blueprint_skills: bool = False,
) -> None:
    files: dict[str, list[dict]] = {
        "_sde.jsonl": [
            {"_key": "sde", "buildNumber": build_number, "releaseDate": "2026-04-11T08:00:00Z"}
        ],
        "categories.jsonl": [
            {"_key": 1, "name": {"en": "Ship", "ru": "Корабль"}, "published": True}
        ],
        "groups.jsonl": [
            {
                "_key": 10,
                "categoryID": 1,
                "name": {"en": "Test Group", "ru": "Тестовая группа"},
                "published": True,
                "anchorable": False,
                "anchored": False,
                "fittableNonSingleton": False,
                "useBasePrice": False,
            }
        ],
        "marketGroups.jsonl": [
            {
                "_key": 100,
                "name": {"en": "Ships", "ru": "Корабли"},
                "description": {"en": "Ships category", "ru": "Категория кораблей"},
                "hasTypes": True,
            }
        ],
        "metaGroups.jsonl": [
            {"_key": 1, "name": {"en": "Tech I", "ru": "Тех I"}}
        ],
        "types.jsonl": [
            {
                "_key": 34,
                "groupID": 10,
                "name": {"en": "Tritanium", "ru": "Тританум"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
            },
            {
                "_key": 35,
                "groupID": 10,
                "name": {"en": "Pyerite", "ru": "Пирит"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
            },
            {
                "_key": 3380,
                "groupID": 10,
                "name": {"en": "Industry", "ru": "Индустрия"},
                "portionSize": 1,
                "published": True,
            },
            {
                "_key": 5001,
                "groupID": 10,
                "name": {"en": "Test Blueprint", "ru": "Тестовый чертеж"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
                "metaGroupID": 1,
            },
            {
                "_key": 5002,
                "groupID": 10,
                "name": {"en": "Test Product", "ru": "Тестовый продукт"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
            },
            {
                "_key": 6001,
                "groupID": 10,
                "name": {"en": "Compressed Tritanium", "ru": "Сжатый тританиум"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
            },
            {
                "_key": 7001,
                "groupID": 10,
                "name": {"en": "Orphan Blueprint", "ru": "Осиротевший чертеж"},
                "portionSize": 1,
                "published": True,
                "marketGroupID": 100,
            },
            {
                "_key": 1531,
                "groupID": 10,
                "name": {"en": "Station Hub", "ru": "Станция"},
                "portionSize": 1,
                "published": True,
            },
        ],
        "dogmaUnits.jsonl": [
            {
                "_key": 1,
                "name": "Length",
                "displayName": {"en": "m", "ru": "м"},
                "description": {"en": "Meter", "ru": "Метр"},
            }
        ],
        "dogmaAttributes.jsonl": [
            {
                "_key": 182,
                "attributeCategoryID": 9,
                "name": "mass",
                "displayName": {"en": "Mass", "ru": "Масса"},
                "description": {"en": "Mass value", "ru": "Значение массы"},
                "published": True,
                "stackable": True,
                "unitID": 1,
            }
        ],
        "dogmaEffects.jsonl": [
            {
                "_key": 596,
                "effectCategoryID": 1,
                "name": "manufacturingBonus",
                "published": True,
                "isAssistance": False,
                "isOffensive": False,
                "isWarpSafe": True,
                "electronicChance": False,
                "propulsionChance": False,
                "rangeChance": False,
                "disallowAutoRepeat": False,
            }
        ],
        "typeDogma.jsonl": [
            {
                "_key": 5002,
                "dogmaAttributes": [{"attributeID": 182, "value": 12.0}],
                "dogmaEffects": [{"effectID": 596, "isDefault": True}],
            }
        ],
        "typeMaterials.jsonl": [
            {"_key": 5002, "materials": [{"materialTypeID": 34, "quantity": 10}]},
            {
                "_key": 6001,
                "randomizedMaterials": [
                    {"materialTypeID": 34, "quantityMin": 5, "quantityMax": 7}
                ],
            },
        ],
        "compressibleTypes.jsonl": [
            {"_key": 34, "compressedTypeID": 6001}
        ],
        "blueprints.jsonl": [
            {
                "_key": 5001,
                "blueprintTypeID": 5001,
                "maxProductionLimit": 300,
                "activities": {
                    "manufacturing": {
                        "materials": [{"typeID": 34, "quantity": 10}],
                        "products": [{"typeID": 5002, "quantity": 1}],
                        "skills": [{"typeID": 3380, "level": 1}],
                        "time": 600,
                    }
                },
            }
        ],
        "mapRegions.jsonl": [
            {
                "_key": 10000001,
                "name": {"en": "Test Region", "ru": "Тестовый регион"},
                "description": {"en": "Region", "ru": "Регион"},
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            }
        ],
        "mapConstellations.jsonl": [
            {
                "_key": 20000001,
                "regionID": 10000001,
                "name": {"en": "Test Constellation", "ru": "Тестовое созвездие"},
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            }
        ],
        "mapSolarSystems.jsonl": [
            {
                "_key": 30000001,
                "regionID": 10000001,
                "constellationID": 20000001,
                "name": {"en": "Test System", "ru": "Тестовая система"},
                "securityStatus": 0.9,
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
                "position2D": {"x": 4.0, "y": 5.0},
                "border": True,
                "hub": True,
                "international": True,
                "regional": True,
            }
        ],
        "npcCorporations.jsonl": [
            {
                "_key": 1000001,
                "name": {"en": "Test Corp", "ru": "Тестовая корпорация"},
                "description": {"en": "Corp", "ru": "Корпа"},
                "tickerName": "TST",
                "deleted": False,
                "solarSystemID": 30000001,
            }
        ],
        "stationOperations.jsonl": [
            {
                "_key": 1,
                "activityID": 1,
                "operationName": {"en": "Factory", "ru": "Фабрика"},
                "description": {"en": "Factory station", "ru": "Фабричная станция"},
                "manufacturingFactor": 0.98,
                "researchFactor": 0.97,
                "border": 0.0,
                "corridor": 0.0,
                "fringe": 0.0,
                "hub": 1.0,
                "ratio": 1,
            }
        ],
        "npcStations.jsonl": [
            {
                "_key": 60000001,
                "solarSystemID": 30000001,
                "ownerID": 1000001,
                "operationID": 1,
                "typeID": 1531,
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
                "reprocessingEfficiency": 0.5,
                "reprocessingHangarFlag": 4,
                "reprocessingStationsTake": 0.05,
                "useOperationName": True,
            }
        ],
        "planetSchematics.jsonl": [
            {
                "_key": 65,
                "cycleTime": 3600,
                "name": {"en": "Coolant", "ru": "Охлаждающая жидкость"},
                "types": [
                    {"_key": 34, "isInput": True, "quantity": 10},
                    {"_key": 5002, "isInput": False, "quantity": 5},
                ],
            }
        ],
    }

    if include_orphan_blueprint_refs:
        files["blueprints.jsonl"].append(
            {
                "_key": 7001,
                "blueprintTypeID": 7001,
                "maxProductionLimit": 300,
                "activities": {
                    "manufacturing": {
                        "materials": [{"typeID": 999991, "quantity": 3}],
                        "products": [{"typeID": 999992, "quantity": 1}],
                        "time": 120,
                    }
                },
            }
        )

    if include_duplicate_blueprint_skills:
        files["blueprints.jsonl"].append(
            {
                "_key": 7002,
                "blueprintTypeID": 7001,
                "maxProductionLimit": 300,
                "activities": {
                    "copying": {
                        "skills": [
                            {"typeID": 3380, "level": 1},
                            {"typeID": 3380, "level": 1},
                        ],
                        "time": 120,
                    }
                },
            }
        )

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, rows in files.items():
            archive.writestr(name, _jsonl_bytes(rows))


class SdeImporterTests(unittest.TestCase):
    def test_import_archive_populates_sqlite_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "sample_sde.zip"
            build_sample_sde_archive(archive_path)

            importer = SdeImporter(temp_path / "tmp")
            version = SdeRemoteVersion(
                build_number=999001,
                release_date=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
                archive_url="https://example.invalid/sample.zip",
                metadata_url="https://example.invalid/latest.jsonl",
            )

            database_path = importer.import_archive(archive_path, version, report_progress=lambda _progress: None)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    8,
                    connection.execute("SELECT COUNT(*) FROM sde_types").fetchone()[0],
                )
                self.assertEqual(
                    1,
                    connection.execute("SELECT COUNT(*) FROM sde_blueprints").fetchone()[0],
                )
                self.assertEqual(
                    1,
                    connection.execute("SELECT COUNT(*) FROM sde_blueprint_activity_materials").fetchone()[0],
                )
                self.assertEqual(
                    1,
                    connection.execute("SELECT COUNT(*) FROM sde_type_randomized_reprocessing_materials").fetchone()[0],
                )
                self.assertEqual(
                    1,
                    connection.execute("SELECT COUNT(*) FROM sde_npc_stations").fetchone()[0],
                )
                self.assertEqual(
                    999001,
                    connection.execute("SELECT build_number FROM sde_catalog_info").fetchone()[0],
                )

    def test_import_archive_keeps_blueprint_links_to_missing_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "sample_sde_orphans.zip"
            build_sample_sde_archive(archive_path, include_orphan_blueprint_refs=True)

            importer = SdeImporter(temp_path / "tmp")
            version = SdeRemoteVersion(
                build_number=999001,
                release_date=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
                archive_url="https://example.invalid/sample.zip",
                metadata_url="https://example.invalid/latest.jsonl",
            )

            database_path = importer.import_archive(archive_path, version, report_progress=lambda _progress: None)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    999991,
                    connection.execute(
                        """
                        SELECT material_type_id
                        FROM sde_blueprint_activity_materials
                        WHERE blueprint_type_id = 7001 AND quantity = 3
                        """
                    ).fetchone()[0],
                )
                self.assertEqual(
                    999992,
                    connection.execute(
                        """
                        SELECT product_type_id
                        FROM sde_blueprint_activity_products
                        WHERE blueprint_type_id = 7001 AND quantity = 1 AND probability IS NULL
                        """
                    ).fetchone()[0],
                )

    def test_import_archive_deduplicates_duplicate_blueprint_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "sample_sde_duplicate_skills.zip"
            build_sample_sde_archive(archive_path, include_duplicate_blueprint_skills=True)

            importer = SdeImporter(temp_path / "tmp")
            version = SdeRemoteVersion(
                build_number=999001,
                release_date=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
                archive_url="https://example.invalid/sample.zip",
                metadata_url="https://example.invalid/latest.jsonl",
            )

            database_path = importer.import_archive(archive_path, version, report_progress=lambda _progress: None)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    1,
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM sde_blueprint_activity_skills
                        WHERE blueprint_type_id = 7001 AND activity_type = 'copying' AND skill_type_id = 3380
                        """
                    ).fetchone()[0],
                )

