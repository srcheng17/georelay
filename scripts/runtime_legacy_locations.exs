# Synthetic public-coordinate legacy evidence; used only on the isolated smoke DB.
import Ecto.Query
alias TeslaMate.{Locations, Log, Repo}
alias TeslaMate.Locations.{Address, LocalIdentities}
alias TeslaMate.Log.{ChargingProcess, Drive}

{1, nil} = Repo.update_all(TeslaMate.Settings.GlobalSettings, set: [language: "en"])

{:error, :identity_store_not_initialized} =
  Locations.find_address(%{latitude: 48.8584, longitude: 2.2945})

original = Jason.decode!(File.read!("/checks/runtime_legacy_identities.json"))
rows = original["identities"]
[osm, keyed | _] = rows

create = fn item, upstream ->
  Locations.create_address(%{
    osm_id: item["osm_id"],
    osm_type: "node",
    latitude: "48.8584",
    longitude: "2.2945",
    display_name: "Fixture Historical",
    name: "Fixture Historical",
    raw: %{"lat" => item["lat"], "lon" => item["lon"], "upstream" => upstream}
  })
end

{:ok, a} = create.(osm, %{"provider" => "osm", "osm_type" => "node", "osm_id" => 123})
{:ok, b} = create.(keyed, %{"provider" => "amap"})

{:ok, positive} =
  Locations.create_address(%{
    osm_id: 42,
    osm_type: "way",
    latitude: "48.8584",
    longitude: "2.2945",
    display_name: "Fixture Positive",
    raw: %{"fixture" => "positive"}
  })

{:ok, car} = Log.create_car(%{eid: 42, vid: 42, vin: "legacy-fixture-not-a-vehicle"})
date = ~U[2024-01-01 00:00:00.000000Z]
{:ok, position} = Log.insert_position(car, %{latitude: 48.8584, longitude: 2.2945, date: date})

drive =
  Repo.insert!(%Drive{
    car_id: car.id,
    start_date: date,
    start_position_id: position.id,
    end_position_id: position.id,
    start_address_id: a.id,
    end_address_id: b.id
  })

charging =
  Repo.insert!(%ChargingProcess{
    car_id: car.id,
    start_date: date,
    position_id: position.id,
    address_id: b.id
  })

snapshot = Repo.all(from(x in Address, order_by: x.id))
false = Repo.exists?(from(x in "georelay_identity_state"))
{:error, _} = LocalIdentities.initialize_fresh(apply: true, fresh_install: true)

path = "/tmp/georelay-smoke-legacy.json"
# A missing referenced row must fail without any partial write or enablement.
File.write!(path, Jason.encode!(Map.put(original, "identities", [osm])))
File.chmod!(path, 0o600)
{:error, _} = LocalIdentities.import_file(path, apply: true)
true = Repo.all(from(x in Address, order_by: x.id)) == snapshot
false = Repo.exists?(from(x in "georelay_identity_state"))

File.write!(path, Jason.encode!(original))

{:ok, %{mode: :preview, addresses: 2, legacy_high_water: 10010}} =
  LocalIdentities.import_file(path)

true = Repo.all(from(x in Address, order_by: x.id)) == snapshot

{:ok, %{mode: :applied, addresses: 2, legacy_high_water: 10010}} =
  LocalIdentities.import_file(path, apply: true)

{:ok, %{mode: :already_initialized}} = LocalIdentities.import_file(path, apply: true)
File.rm!(path)

for {before, item} <- [{a, osm}, {b, keyed}] do
  restored = Repo.get!(Address, before.id)

  true =
    Map.take(restored, [:id, :osm_id, :osm_type]) == Map.take(before, [:id, :osm_id, :osm_type])

  true = Decimal.equal?(restored.latitude, item["lat"])
  true = Decimal.equal?(restored.longitude, item["lon"])
  true = restored.raw["georelay"] == Map.put(item["context"], "version", 1)

  {:ok, ^restored} =
    Locations.find_address(%{latitude: restored.latitude, longitude: restored.longitude})
end

false = Decimal.equal?(Repo.get!(Address, a.id).latitude, Repo.get!(Address, b.id).latitude)
true = Repo.get!(Address, positive.id) == positive
true = Repo.get!(Drive, drive.id) == drive
true = Repo.get!(ChargingProcess, charging.id) == charging
true = Repo.get!(TeslaMate.Log.Position, position.id) == position
3 = Repo.aggregate(Address, :count, :id)
# The unreferenced SQLite row is not materialized, but its entire allocation range is reserved.
{:error, _} = Locations.find_address(%{latitude: Decimal.new("49"), longitude: Decimal.new("3")})
%{rows: [[last_value]]} = Repo.query!("SELECT last_value FROM georelay_address_identity_seq")
true = last_value < -10010
3 = Repo.aggregate(Address, :count, :id)
true = Repo.get!(Drive, drive.id) == drive

{:ok, response} =
  Finch.build(:get, "http://stub:8080/legacy-assertions")
  |> Finch.request(TeslaMate.HTTP, receive_timeout: 5_000)

200 = response.status
%{"ok" => true} = Jason.decode!(response.body)
IO.puts("GEORELAY_RUNTIME_LEGACY_OK")
