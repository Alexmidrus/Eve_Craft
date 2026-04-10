from __future__ import annotations

import logging
import zipfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.sde.domain.models import SdeRemoteVersion
from eve_craft.platform.sde.infrastructure.archive import (
    iter_jsonl,
    localized_name_en,
    localized_name_ru,
    localized_text,
)
from eve_craft.platform.sde.infrastructure.models import (
    SdeBase,
    SdeBlueprint,
    SdeBlueprintActivity,
    SdeBlueprintActivityMaterial,
    SdeBlueprintActivityProduct,
    SdeBlueprintActivitySkill,
    SdeCatalogInfo,
    SdeCategory,
    SdeCompressibleType,
    SdeConstellation,
    SdeDogmaAttribute,
    SdeDogmaEffect,
    SdeDogmaUnit,
    SdeGroup,
    SdeMarketGroup,
    SdeMetaGroup,
    SdeNpcCorporation,
    SdeNpcStation,
    SdePlanetSchematic,
    SdePlanetSchematicType,
    SdeRegion,
    SdeSolarSystem,
    SdeStationOperation,
    SdeType,
    SdeTypeDogmaAttribute,
    SdeTypeDogmaEffect,
    SdeTypeRandomizedReprocessingMaterial,
    SdeTypeReprocessingMaterial,
)
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)

ImportHandler = tuple[str, str]


class SdeImporter:
    IMPORT_SEQUENCE: tuple[ImportHandler, ...] = (
        ("categories.jsonl", "import_categories"),
        ("groups.jsonl", "import_groups"),
        ("marketGroups.jsonl", "import_market_groups"),
        ("metaGroups.jsonl", "import_meta_groups"),
        ("types.jsonl", "import_types"),
        ("dogmaUnits.jsonl", "import_dogma_units"),
        ("dogmaAttributes.jsonl", "import_dogma_attributes"),
        ("dogmaEffects.jsonl", "import_dogma_effects"),
        ("typeDogma.jsonl", "import_type_dogma"),
        ("typeMaterials.jsonl", "import_type_materials"),
        ("compressibleTypes.jsonl", "import_compressible_types"),
        ("blueprints.jsonl", "import_blueprints"),
        ("mapRegions.jsonl", "import_regions"),
        ("mapConstellations.jsonl", "import_constellations"),
        ("mapSolarSystems.jsonl", "import_solar_systems"),
        ("npcCorporations.jsonl", "import_npc_corporations"),
        ("stationOperations.jsonl", "import_station_operations"),
        ("npcStations.jsonl", "import_npc_stations"),
        ("planetSchematics.jsonl", "import_planet_schematics"),
    )

    def __init__(self, temporary_dir: Path) -> None:
        self._temporary_dir = temporary_dir

    def import_archive(
        self,
        archive_path: Path,
        version: SdeRemoteVersion,
        report_progress,
    ) -> Path:
        self._temporary_dir.mkdir(parents=True, exist_ok=True)
        temp_database_path = self._temporary_dir / f"sde_build_{version.build_number}.sqlite3"

        if temp_database_path.exists():
            temp_database_path.unlink()

        database = DatabaseManager(temp_database_path)
        try:
            SdeBase.metadata.create_all(database.engine)
            with database.engine.begin() as connection:
                with zipfile.ZipFile(archive_path) as archive:
                    self._validate_archive_contents(archive)
                    total_steps = len(self.IMPORT_SEQUENCE)

                    for step_index, (file_name, handler_name) in enumerate(self.IMPORT_SEQUENCE, start=1):
                        step_percent = int((step_index - 1) * 100 / total_steps)
                        report_progress(
                            OperationProgress(
                                stage="sde_import",
                                message=f"Importing {file_name}",
                                percent=step_percent,
                                detail=f"Step {step_index} of {total_steps}",
                            )
                        )
                        with archive.open(file_name) as file_handle:
                            row_count = getattr(self, handler_name)(connection, iter_jsonl(file_handle))
                        LOGGER.info("Imported %s rows from %s.", row_count, file_name)

                    connection.execute(
                        SdeCatalogInfo.__table__.insert(),
                        [
                            {
                                "id": 1,
                                "build_number": version.build_number,
                                "release_date": version.release_date,
                                "imported_at": datetime.now(timezone.utc),
                                "archive_url": version.archive_url,
                                "archive_etag": version.etag,
                                "archive_last_modified": version.last_modified,
                            }
                        ],
                    )

            database.dispose()
            LOGGER.info("SDE archive imported into %s.", temp_database_path)
            return temp_database_path
        except Exception:
            database.dispose()
            if temp_database_path.exists():
                temp_database_path.unlink()
            raise

    def import_categories(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeCategory.__table__,
            (
                {
                    "category_id": row["_key"],
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "icon_id": row.get("iconID"),
                    "published": row.get("published", False),
                }
                for row in rows
            ),
        )

    def import_groups(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeGroup.__table__,
            (
                {
                    "group_id": row["_key"],
                    "category_id": row["categoryID"],
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "icon_id": row.get("iconID"),
                    "published": row.get("published", False),
                    "anchorable": row.get("anchorable", False),
                    "anchored": row.get("anchored", False),
                    "fittable_non_singleton": row.get("fittableNonSingleton", False),
                    "use_base_price": row.get("useBasePrice", False),
                }
                for row in rows
            ),
        )

    def import_market_groups(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeMarketGroup.__table__,
            (
                {
                    "market_group_id": row["_key"],
                    "parent_group_id": row.get("parentGroupID"),
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "icon_id": row.get("iconID"),
                    "has_types": row.get("hasTypes", False),
                }
                for row in rows
            ),
        )

    def import_meta_groups(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeMetaGroup.__table__,
            (
                {
                    "meta_group_id": row["_key"],
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "icon_id": row.get("iconID"),
                    "icon_suffix": row.get("iconSuffix"),
                    "color_r": (row.get("color") or {}).get("r"),
                    "color_g": (row.get("color") or {}).get("g"),
                    "color_b": (row.get("color") or {}).get("b"),
                }
                for row in rows
            ),
        )

    def import_types(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeType.__table__,
            (
                {
                    "type_id": row["_key"],
                    "group_id": row["groupID"],
                    "market_group_id": row.get("marketGroupID"),
                    "meta_group_id": row.get("metaGroupID"),
                    "race_id": row.get("raceID"),
                    "icon_id": row.get("iconID"),
                    "graphic_id": row.get("graphicID"),
                    "faction_id": row.get("factionID"),
                    "variation_parent_type_id": row.get("variationParentTypeID"),
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "published": row.get("published", False),
                    "portion_size": row.get("portionSize", 1),
                    "volume": row.get("volume"),
                    "capacity": row.get("capacity"),
                    "mass": row.get("mass"),
                    "radius": row.get("radius"),
                    "base_price": row.get("basePrice"),
                    "meta_level": row.get("metaLevel"),
                }
                for row in rows
            ),
        )

    def import_dogma_units(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeDogmaUnit.__table__,
            (
                {
                    "unit_id": row["_key"],
                    "name": row["name"],
                    "display_name_en": localized_text(row, "displayName", "en"),
                    "display_name_ru": localized_text(row, "displayName", "ru"),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                }
                for row in rows
            ),
        )

    def import_dogma_attributes(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeDogmaAttribute.__table__,
            (
                {
                    "attribute_id": row["_key"],
                    "attribute_category_id": row.get("attributeCategoryID"),
                    "unit_id": row.get("unitID"),
                    "icon_id": row.get("iconID"),
                    "name": row["name"],
                    "display_name_en": localized_text(row, "displayName", "en"),
                    "display_name_ru": localized_text(row, "displayName", "ru"),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "tooltip_title_en": localized_text(row, "tooltipTitle", "en"),
                    "tooltip_title_ru": localized_text(row, "tooltipTitle", "ru"),
                    "tooltip_description_en": localized_text(row, "tooltipDescription", "en"),
                    "tooltip_description_ru": localized_text(row, "tooltipDescription", "ru"),
                    "data_type": row.get("dataType"),
                    "default_value": row.get("defaultValue"),
                    "display_when_zero": row.get("displayWhenZero"),
                    "high_is_good": row.get("highIsGood"),
                    "published": row.get("published", False),
                    "stackable": row.get("stackable", False),
                }
                for row in rows
            ),
        )

    def import_dogma_effects(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeDogmaEffect.__table__,
            (
                {
                    "effect_id": row["_key"],
                    "effect_category_id": row["effectCategoryID"],
                    "name": row.get("name"),
                    "guid": row.get("guid"),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "display_name_en": localized_text(row, "displayName", "en"),
                    "display_name_ru": localized_text(row, "displayName", "ru"),
                    "icon_id": row.get("iconID"),
                    "discharge_attribute_id": row.get("dischargeAttributeID"),
                    "duration_attribute_id": row.get("durationAttributeID"),
                    "falloff_attribute_id": row.get("falloffAttributeID"),
                    "range_attribute_id": row.get("rangeAttributeID"),
                    "tracking_speed_attribute_id": row.get("trackingSpeedAttributeID"),
                    "npc_usage_chance_attribute_id": row.get("npcUsageChanceAttributeID"),
                    "npc_activation_chance_attribute_id": row.get("npcActivationChanceAttributeID"),
                    "fitting_usage_chance_attribute_id": row.get("fittingUsageChanceAttributeID"),
                    "resistance_attribute_id": row.get("resistanceAttributeID"),
                    "published": row.get("published", False),
                    "is_assistance": row.get("isAssistance", False),
                    "is_offensive": row.get("isOffensive", False),
                    "is_warp_safe": row.get("isWarpSafe", False),
                    "electronic_chance": row.get("electronicChance", False),
                    "propulsion_chance": row.get("propulsionChance", False),
                    "range_chance": row.get("rangeChance", False),
                    "disallow_auto_repeat": row.get("disallowAutoRepeat", False),
                }
                for row in rows
            ),
        )

    def import_type_dogma(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        attributes: list[dict[str, Any]] = []
        effects: list[dict[str, Any]] = []

        for row in rows:
            type_id = row["_key"]
            for attribute in row.get("dogmaAttributes", []):
                attributes.append(
                    {
                        "type_id": type_id,
                        "attribute_id": attribute["attributeID"],
                        "value": attribute["value"],
                    }
                )
            for effect in row.get("dogmaEffects", []):
                effects.append(
                    {
                        "type_id": type_id,
                        "effect_id": effect["effectID"],
                        "is_default": effect.get("isDefault", False),
                    }
                )

        inserted = self._insert_rows(connection, SdeTypeDogmaAttribute.__table__, attributes)
        inserted += self._insert_rows(connection, SdeTypeDogmaEffect.__table__, effects)
        return inserted

    def import_type_materials(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        materials: list[dict[str, Any]] = []
        randomized_materials: list[dict[str, Any]] = []

        for row in rows:
            type_id = row["_key"]
            for material in row.get("materials", []):
                materials.append(
                    {
                        "type_id": type_id,
                        "material_type_id": material["materialTypeID"],
                        "quantity": material["quantity"],
                    }
                )

            for material in row.get("randomizedMaterials", []):
                randomized_materials.append(
                    {
                        "type_id": type_id,
                        "material_type_id": material["materialTypeID"],
                        "quantity_min": material["quantityMin"],
                        "quantity_max": material["quantityMax"],
                    }
                )

        inserted = self._insert_rows(connection, SdeTypeReprocessingMaterial.__table__, materials)
        inserted += self._insert_rows(
            connection,
            SdeTypeRandomizedReprocessingMaterial.__table__,
            randomized_materials,
        )
        return inserted

    def import_compressible_types(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeCompressibleType.__table__,
            (
                {
                    "type_id": row["_key"],
                    "compressed_type_id": row["compressedTypeID"],
                }
                for row in rows
            ),
        )

    def import_blueprints(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        blueprints: dict[int, dict[str, Any]] = {}
        activities: dict[tuple[int, str], dict[str, Any]] = {}
        materials: dict[tuple[int, str, int], dict[str, Any]] = {}
        products: dict[tuple[int, str, int], dict[str, Any]] = {}
        skills: dict[tuple[int, str, int], dict[str, Any]] = {}

        for row in rows:
            blueprint_type_id = row["blueprintTypeID"]
            blueprints[blueprint_type_id] = {
                "blueprint_type_id": blueprint_type_id,
                "max_production_limit": row["maxProductionLimit"],
            }

            for activity_type, activity_payload in row.get("activities", {}).items():
                activities[(blueprint_type_id, activity_type)] = {
                    "blueprint_type_id": blueprint_type_id,
                    "activity_type": activity_type,
                    "time_seconds": activity_payload.get("time"),
                }

                for material in activity_payload.get("materials", []):
                    materials[(blueprint_type_id, activity_type, material["typeID"])] = {
                        "blueprint_type_id": blueprint_type_id,
                        "activity_type": activity_type,
                        "material_type_id": material["typeID"],
                        "quantity": material["quantity"],
                    }

                for product in activity_payload.get("products", []):
                    products[(blueprint_type_id, activity_type, product["typeID"])] = {
                        "blueprint_type_id": blueprint_type_id,
                        "activity_type": activity_type,
                        "product_type_id": product["typeID"],
                        "quantity": product["quantity"],
                        "probability": product.get("probability"),
                    }

                for skill in activity_payload.get("skills", []):
                    skills[(blueprint_type_id, activity_type, skill["typeID"])] = {
                        "blueprint_type_id": blueprint_type_id,
                        "activity_type": activity_type,
                        "skill_type_id": skill["typeID"],
                        "level": skill["level"],
                    }

        inserted = self._insert_rows(connection, SdeBlueprint.__table__, blueprints.values())
        inserted += self._insert_rows(connection, SdeBlueprintActivity.__table__, activities.values())
        inserted += self._insert_rows(connection, SdeBlueprintActivityMaterial.__table__, materials.values())
        inserted += self._insert_rows(connection, SdeBlueprintActivityProduct.__table__, products.values())
        inserted += self._insert_rows(connection, SdeBlueprintActivitySkill.__table__, skills.values())
        return inserted

    def import_regions(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeRegion.__table__,
            (
                {
                    "region_id": row["_key"],
                    "faction_id": row.get("factionID"),
                    "nebula_id": row.get("nebulaID"),
                    "wormhole_class_id": row.get("wormholeClassID"),
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "position_x": (row.get("position") or {}).get("x"),
                    "position_y": (row.get("position") or {}).get("y"),
                    "position_z": (row.get("position") or {}).get("z"),
                }
                for row in rows
            ),
        )

    def import_constellations(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeConstellation.__table__,
            (
                {
                    "constellation_id": row["_key"],
                    "region_id": row["regionID"],
                    "faction_id": row.get("factionID"),
                    "wormhole_class_id": row.get("wormholeClassID"),
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "position_x": (row.get("position") or {}).get("x"),
                    "position_y": (row.get("position") or {}).get("y"),
                    "position_z": (row.get("position") or {}).get("z"),
                }
                for row in rows
            ),
        )

    def import_solar_systems(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeSolarSystem.__table__,
            (
                {
                    "solar_system_id": row["_key"],
                    "region_id": row["regionID"],
                    "constellation_id": row["constellationID"],
                    "star_id": row.get("starID"),
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "security_class": row.get("securityClass"),
                    "security_status": row.get("securityStatus"),
                    "position_x": (row.get("position") or {}).get("x"),
                    "position_y": (row.get("position") or {}).get("y"),
                    "position_z": (row.get("position") or {}).get("z"),
                    "position_2d_x": (row.get("position2D") or {}).get("x"),
                    "position_2d_y": (row.get("position2D") or {}).get("y"),
                    "luminosity": row.get("luminosity"),
                    "radius": row.get("radius"),
                    "border": row.get("border", False),
                    "corridor": row.get("corridor", False),
                    "hub": row.get("hub", False),
                    "international": row.get("international", False),
                    "regional": row.get("regional", False),
                }
                for row in rows
            ),
        )

    def import_npc_corporations(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeNpcCorporation.__table__,
            (
                {
                    "corporation_id": row["_key"],
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                    "ticker_name": row.get("tickerName"),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "faction_id": row.get("factionID"),
                    "solar_system_id": row.get("solarSystemID"),
                    "station_id": row.get("stationID"),
                    "race_id": row.get("raceID"),
                    "size": row.get("size"),
                    "extent": row.get("extent"),
                    "min_security": row.get("minSecurity"),
                    "deleted": row.get("deleted", False),
                }
                for row in rows
            ),
        )

    def import_station_operations(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeStationOperation.__table__,
            (
                {
                    "operation_id": row["_key"],
                    "activity_id": row.get("activityID"),
                    "operation_name_en": localized_text(row, "operationName", "en"),
                    "operation_name_ru": localized_text(row, "operationName", "ru"),
                    "description_en": localized_text(row, "description", "en"),
                    "description_ru": localized_text(row, "description", "ru"),
                    "border": row.get("border"),
                    "corridor": row.get("corridor"),
                    "fringe": row.get("fringe"),
                    "hub": row.get("hub"),
                    "ratio": row.get("ratio"),
                    "manufacturing_factor": row.get("manufacturingFactor"),
                    "research_factor": row.get("researchFactor"),
                }
                for row in rows
            ),
        )

    def import_npc_stations(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        return self._insert_rows(
            connection,
            SdeNpcStation.__table__,
            (
                {
                    "station_id": row["_key"],
                    "solar_system_id": row["solarSystemID"],
                    "owner_id": row["ownerID"],
                    "operation_id": row["operationID"],
                    "type_id": row["typeID"],
                    "orbit_id": row.get("orbitID"),
                    "orbit_index": row.get("orbitIndex"),
                    "celestial_index": row.get("celestialIndex"),
                    "position_x": (row.get("position") or {}).get("x"),
                    "position_y": (row.get("position") or {}).get("y"),
                    "position_z": (row.get("position") or {}).get("z"),
                    "reprocessing_efficiency": row.get("reprocessingEfficiency"),
                    "reprocessing_hangar_flag": row.get("reprocessingHangarFlag"),
                    "reprocessing_stations_take": row.get("reprocessingStationsTake"),
                    "use_operation_name": row.get("useOperationName"),
                }
                for row in rows
            ),
        )

    def import_planet_schematics(self, connection: Connection, rows: Iterable[dict[str, Any]]) -> int:
        schematics: list[dict[str, Any]] = []
        schematic_types: list[dict[str, Any]] = []

        for row in rows:
            schematic_id = row["_key"]
            schematics.append(
                {
                    "schematic_id": schematic_id,
                    "cycle_time": row["cycleTime"],
                    "name_en": localized_name_en(row),
                    "name_ru": localized_name_ru(row),
                }
            )

            for type_payload in row.get("types", []):
                schematic_types.append(
                    {
                        "schematic_id": schematic_id,
                        "type_id": type_payload["_key"],
                        "quantity": type_payload["quantity"],
                        "is_input": type_payload["isInput"],
                    }
                )

        inserted = self._insert_rows(connection, SdePlanetSchematic.__table__, schematics)
        inserted += self._insert_rows(connection, SdePlanetSchematicType.__table__, schematic_types)
        return inserted

    def _validate_archive_contents(self, archive: zipfile.ZipFile) -> None:
        available = set(archive.namelist())
        required = {file_name for file_name, _handler_name in self.IMPORT_SEQUENCE}
        missing = sorted(required - available)

        if missing:
            raise RuntimeError(f"SDE archive is missing required files: {', '.join(missing)}")

    def _insert_rows(
        self,
        connection: Connection,
        table,
        rows: Iterable[dict[str, Any]],
        chunk_size: int = 1000,
    ) -> int:
        inserted = 0
        chunk: list[dict[str, Any]] = []

        for row in rows:
            chunk.append(row)
            if len(chunk) >= chunk_size:
                connection.execute(table.insert(), chunk)
                inserted += len(chunk)
                chunk.clear()

        if chunk:
            connection.execute(table.insert(), chunk)
            inserted += len(chunk)

        return inserted

