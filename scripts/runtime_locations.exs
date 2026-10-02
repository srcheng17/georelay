# Only mounted into the isolated release and its newly migrated fixture database.
import Ecto.Query
alias TeslaMate.{Locations, Log, Repo}
alias TeslaMate.Locations.Address
alias TeslaMate.Log.{ChargingProcess, Drive}

{1, nil} = Repo.update_all(TeslaMate.Settings.GlobalSettings, set: [language: "en"])
point = %{latitude: 48.8584, longitude: 2.2945}
{:ok, local} = Locations.find_address(point)
true = local.osm_id == -10_001 and local.osm_type == "node"
true = Decimal.equal?(local.latitude, "48.8584") and Decimal.equal?(local.longitude, "2.2945")
true = local.name == "Fixture Original" and local.raw["fixture"] == "original"
{:ok, ^local} = Locations.find_address(point)

{:ok, legacy} =
  Locations.create_address(%{
    osm_id: 42,
    osm_type: "way",
    latitude: "48.8584",
    longitude: "2.2945",
    display_name: "Fixture Historical Address",
    name: "Fixture Historical",
    raw: %{"fixture" => "historical"}
  })

{:ok, car} = Log.create_car(%{eid: 42, vid: 42, vin: "runtime-fixture-not-a-vehicle"})
date = ~U[2024-01-01 00:00:00.000000Z]
{:ok, position} = Log.insert_position(car, Map.put(point, :date, date))
drive = Repo.insert!(%Drive{
  car_id: car.id, start_date: date, start_position_id: position.id,
  end_position_id: position.id, start_address_id: legacy.id, end_address_id: local.id
})
charging = Repo.insert!(%ChargingProcess{
  car_id: car.id, start_date: date, position_id: position.id, address_id: local.id
})

:ok = Locations.refresh_addresses("zh-CN")
updated = Repo.get!(Address, local.id)
identity = [:id, :osm_id, :osm_type, :latitude, :longitude]
true = Map.take(updated, identity) == Map.take(local, identity)
true = Map.take(updated, [:name, :display_name, :road, :house_number, :postcode]) == %{
  name: "Fixture Updated", display_name: "Fixture Updated Address",
  road: "Fixture Updated Road", house_number: "2", postcode: "75007"
}
true = updated.raw["fixture"] == "refreshed" and updated.raw["lat"] == "49.0"
true = Repo.get!(Address, legacy.id) == legacy
true = Repo.get!(Drive, drive.id) == drive
true = Repo.get!(ChargingProcess, charging.id) == charging
true = Repo.get!(TeslaMate.Log.Position, position.id) == position
snapshot = Repo.all(from a in Address, order_by: a.id)
2 = length(snapshot)

{:error, :missing_local_address} = Locations.refresh_addresses("missing")
true = Repo.all(from a in Address, order_by: a.id) == snapshot
{:error, "fixture_provider_failure"} = Locations.refresh_addresses("provider-fail")
true = Repo.all(from a in Address, order_by: a.id) == snapshot
{:error, "fixture_provider_failure"} = Locations.find_address(%{point | latitude: 48.8585})
true = Repo.all(from a in Address, order_by: a.id) == snapshot
true = Repo.get!(Drive, drive.id) == drive
true = Repo.get!(ChargingProcess, charging.id) == charging
true = Enum.all?(snapshot, &(&1.osm_type != "unknown" and &1.display_name != "Unknown"))

{:ok, response} = Finch.build(:get, "http://stub:8080/assertions")
  |> Finch.request(TeslaMate.HTTP, receive_timeout: 5_000)
200 = response.status
%{"ok" => true} = Jason.decode!(response.body)
IO.puts("GEORELAY_RUNTIME_LOCATIONS_OK")
