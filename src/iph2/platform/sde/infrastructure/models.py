from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SdeBase(DeclarativeBase):
    pass


class SdeCatalogInfo(SdeBase):
    __tablename__ = "sde_catalog_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    build_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    release_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archive_url: Mapped[str] = mapped_column(String(512), nullable=False)
    archive_etag: Mapped[str | None] = mapped_column(String(255))
    archive_last_modified: Mapped[str | None] = mapped_column(String(255))


class SdeCategory(SdeBase):
    __tablename__ = "sde_categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    icon_id: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeGroup(SdeBase):
    __tablename__ = "sde_groups"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("sde_categories.category_id"), index=True)
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    icon_id: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False)
    anchorable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    anchored: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fittable_non_singleton: Mapped[bool] = mapped_column(Boolean, nullable=False)
    use_base_price: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeMarketGroup(SdeBase):
    __tablename__ = "sde_market_groups"

    market_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    icon_id: Mapped[int | None] = mapped_column(Integer)
    has_types: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeMetaGroup(SdeBase):
    __tablename__ = "sde_meta_groups"

    meta_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    icon_id: Mapped[int | None] = mapped_column(Integer)
    icon_suffix: Mapped[str | None] = mapped_column(String(64))
    color_r: Mapped[float | None] = mapped_column(Float)
    color_g: Mapped[float | None] = mapped_column(Float)
    color_b: Mapped[float | None] = mapped_column(Float)


class SdeType(SdeBase):
    __tablename__ = "sde_types"

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("sde_groups.group_id"), index=True)
    market_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    meta_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    race_id: Mapped[int | None] = mapped_column(Integer)
    icon_id: Mapped[int | None] = mapped_column(Integer)
    graphic_id: Mapped[int | None] = mapped_column(Integer)
    faction_id: Mapped[int | None] = mapped_column(Integer)
    variation_parent_type_id: Mapped[int | None] = mapped_column(Integer)
    name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    name_ru: Mapped[str | None] = mapped_column(String(255), index=True)
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    portion_size: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    capacity: Mapped[float | None] = mapped_column(Float)
    mass: Mapped[float | None] = mapped_column(Float)
    radius: Mapped[float | None] = mapped_column(Float)
    base_price: Mapped[float | None] = mapped_column(Float)
    meta_level: Mapped[int | None] = mapped_column(Integer)


class SdeDogmaUnit(SdeBase):
    __tablename__ = "sde_dogma_units"

    unit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name_en: Mapped[str | None] = mapped_column(String(255))
    display_name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)


class SdeDogmaAttribute(SdeBase):
    __tablename__ = "sde_dogma_attributes"

    attribute_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attribute_category_id: Mapped[int | None] = mapped_column(Integer, index=True)
    unit_id: Mapped[int | None] = mapped_column(Integer)
    icon_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name_en: Mapped[str | None] = mapped_column(String(255))
    display_name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    tooltip_title_en: Mapped[str | None] = mapped_column(String(255))
    tooltip_title_ru: Mapped[str | None] = mapped_column(String(255))
    tooltip_description_en: Mapped[str | None] = mapped_column(Text)
    tooltip_description_ru: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[int | None] = mapped_column(Integer)
    default_value: Mapped[float | None] = mapped_column(Float)
    display_when_zero: Mapped[bool | None] = mapped_column(Boolean)
    high_is_good: Mapped[bool | None] = mapped_column(Boolean)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeDogmaEffect(SdeBase):
    __tablename__ = "sde_dogma_effects"

    effect_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    effect_category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    guid: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    display_name_en: Mapped[str | None] = mapped_column(String(255))
    display_name_ru: Mapped[str | None] = mapped_column(String(255))
    icon_id: Mapped[int | None] = mapped_column(Integer)
    discharge_attribute_id: Mapped[int | None] = mapped_column(Integer)
    duration_attribute_id: Mapped[int | None] = mapped_column(Integer)
    falloff_attribute_id: Mapped[int | None] = mapped_column(Integer)
    range_attribute_id: Mapped[int | None] = mapped_column(Integer)
    tracking_speed_attribute_id: Mapped[int | None] = mapped_column(Integer)
    npc_usage_chance_attribute_id: Mapped[int | None] = mapped_column(Integer)
    npc_activation_chance_attribute_id: Mapped[int | None] = mapped_column(Integer)
    fitting_usage_chance_attribute_id: Mapped[int | None] = mapped_column(Integer)
    resistance_attribute_id: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_assistance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_offensive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_warp_safe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    electronic_chance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    propulsion_chance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    range_chance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disallow_auto_repeat: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeTypeDogmaAttribute(SdeBase):
    __tablename__ = "sde_type_dogma_attributes"

    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("sde_dogma_attributes.attribute_id"),
        primary_key=True,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)


class SdeTypeDogmaEffect(SdeBase):
    __tablename__ = "sde_type_dogma_effects"

    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    effect_id: Mapped[int] = mapped_column(
        ForeignKey("sde_dogma_effects.effect_id"),
        primary_key=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeBlueprint(SdeBase):
    __tablename__ = "sde_blueprints"

    blueprint_type_id: Mapped[int] = mapped_column(
        ForeignKey("sde_types.type_id"),
        primary_key=True,
    )
    max_production_limit: Mapped[int] = mapped_column(Integer, nullable=False)


class SdeBlueprintActivity(SdeBase):
    __tablename__ = "sde_blueprint_activities"

    blueprint_type_id: Mapped[int] = mapped_column(
        ForeignKey("sde_blueprints.blueprint_type_id"),
        primary_key=True,
    )
    activity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    time_seconds: Mapped[int | None] = mapped_column(Integer)


class SdeBlueprintActivityMaterial(SdeBase):
    __tablename__ = "sde_blueprint_activity_materials"

    blueprint_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    material_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class SdeBlueprintActivityProduct(SdeBase):
    __tablename__ = "sde_blueprint_activity_products"

    blueprint_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[float | None] = mapped_column(Float)


class SdeBlueprintActivitySkill(SdeBase):
    __tablename__ = "sde_blueprint_activity_skills"

    blueprint_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class SdeTypeReprocessingMaterial(SdeBase):
    __tablename__ = "sde_type_reprocessing_materials"

    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    material_type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class SdeTypeRandomizedReprocessingMaterial(SdeBase):
    __tablename__ = "sde_type_randomized_reprocessing_materials"

    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    material_type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    quantity_min: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_max: Mapped[int] = mapped_column(Integer, nullable=False)


class SdeCompressibleType(SdeBase):
    __tablename__ = "sde_compressible_types"

    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    compressed_type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), nullable=False)


class SdePlanetSchematic(SdeBase):
    __tablename__ = "sde_planet_schematics"

    schematic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_time: Mapped[int] = mapped_column(Integer, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))


class SdePlanetSchematicType(SdeBase):
    __tablename__ = "sde_planet_schematic_types"

    schematic_id: Mapped[int] = mapped_column(
        ForeignKey("sde_planet_schematics.schematic_id"),
        primary_key=True,
    )
    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_input: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeRegion(SdeBase):
    __tablename__ = "sde_regions"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faction_id: Mapped[int | None] = mapped_column(Integer, index=True)
    nebula_id: Mapped[int | None] = mapped_column(Integer)
    wormhole_class_id: Mapped[int | None] = mapped_column(Integer)
    name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    position_z: Mapped[float | None] = mapped_column(Float)


class SdeConstellation(SdeBase):
    __tablename__ = "sde_constellations"

    constellation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("sde_regions.region_id"), index=True)
    faction_id: Mapped[int | None] = mapped_column(Integer, index=True)
    wormhole_class_id: Mapped[int | None] = mapped_column(Integer)
    name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    name_ru: Mapped[str | None] = mapped_column(String(255))
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    position_z: Mapped[float | None] = mapped_column(Float)


class SdeSolarSystem(SdeBase):
    __tablename__ = "sde_solar_systems"

    solar_system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("sde_regions.region_id"), index=True)
    constellation_id: Mapped[int] = mapped_column(
        ForeignKey("sde_constellations.constellation_id"),
        index=True,
    )
    star_id: Mapped[int | None] = mapped_column(Integer)
    name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    name_ru: Mapped[str | None] = mapped_column(String(255))
    security_class: Mapped[str | None] = mapped_column(String(8))
    security_status: Mapped[float | None] = mapped_column(Float, index=True)
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    position_z: Mapped[float | None] = mapped_column(Float)
    position_2d_x: Mapped[float | None] = mapped_column(Float)
    position_2d_y: Mapped[float | None] = mapped_column(Float)
    luminosity: Mapped[float | None] = mapped_column(Float)
    radius: Mapped[float | None] = mapped_column(Float)
    border: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corridor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hub: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    international: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SdeNpcCorporation(SdeBase):
    __tablename__ = "sde_npc_corporations"

    corporation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    name_ru: Mapped[str | None] = mapped_column(String(255))
    ticker_name: Mapped[str | None] = mapped_column(String(16))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    faction_id: Mapped[int | None] = mapped_column(Integer, index=True)
    solar_system_id: Mapped[int | None] = mapped_column(Integer)
    station_id: Mapped[int | None] = mapped_column(Integer)
    race_id: Mapped[int | None] = mapped_column(Integer)
    size: Mapped[str | None] = mapped_column(String(8))
    extent: Mapped[str | None] = mapped_column(String(8))
    min_security: Mapped[float | None] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SdeStationOperation(SdeBase):
    __tablename__ = "sde_station_operations"

    operation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    operation_name_en: Mapped[str | None] = mapped_column(String(255), index=True)
    operation_name_ru: Mapped[str | None] = mapped_column(String(255))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ru: Mapped[str | None] = mapped_column(Text)
    border: Mapped[float | None] = mapped_column(Float)
    corridor: Mapped[float | None] = mapped_column(Float)
    fringe: Mapped[float | None] = mapped_column(Float)
    hub: Mapped[float | None] = mapped_column(Float)
    ratio: Mapped[int | None] = mapped_column(Integer)
    manufacturing_factor: Mapped[float | None] = mapped_column(Float)
    research_factor: Mapped[float | None] = mapped_column(Float)


class SdeNpcStation(SdeBase):
    __tablename__ = "sde_npc_stations"

    station_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solar_system_id: Mapped[int] = mapped_column(
        ForeignKey("sde_solar_systems.solar_system_id"),
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("sde_npc_corporations.corporation_id"), index=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("sde_station_operations.operation_id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("sde_types.type_id"))
    orbit_id: Mapped[int | None] = mapped_column(Integer)
    orbit_index: Mapped[int | None] = mapped_column(Integer)
    celestial_index: Mapped[int | None] = mapped_column(Integer)
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    position_z: Mapped[float | None] = mapped_column(Float)
    reprocessing_efficiency: Mapped[float | None] = mapped_column(Float)
    reprocessing_hangar_flag: Mapped[int | None] = mapped_column(Integer)
    reprocessing_stations_take: Mapped[float | None] = mapped_column(Float)
    use_operation_name: Mapped[bool | None] = mapped_column(Boolean)


Index("ix_sde_blueprint_activities_type", SdeBlueprintActivity.blueprint_type_id, SdeBlueprintActivity.activity_type)
Index("ix_sde_blueprint_products_lookup", SdeBlueprintActivityProduct.product_type_id, SdeBlueprintActivityProduct.activity_type)
Index("ix_sde_reprocessing_materials_lookup", SdeTypeReprocessingMaterial.material_type_id)
Index("ix_sde_type_dogma_attribute_lookup", SdeTypeDogmaAttribute.attribute_id, SdeTypeDogmaAttribute.type_id)
