# Only mounted into the isolated compiled release and its new fixture database.
import Ecto.Query
alias TeslaMate.{Locations, Log, Repo}
alias TeslaMate.Locations.{Address, LocalIdentities}
alias TeslaMate.Log.{ChargingProcess, Drive}

{:ok, _} = LocalIdentities.initialize_fresh(apply: true, fresh_install: true)
{1, nil} = Repo.update_all(TeslaMate.Settings.GlobalSettings, set: [language: "en"])
point = %{latitude: Decimal.new("48.858400123"), longitude: Decimal.new("2.294500456")}
{:ok, local} = Locations.find_address(point)
true = local.osm_id < 0 and local.osm_type == "node"

true =
  Decimal.equal?(local.latitude, point.latitude) and
    Decimal.equal?(local.longitude, point.longitude)

true = local.name == "Fixture Original" and local.raw["fixture"] == "original"
true = local.raw["georelay"]["source_osm_id"] == 123
true = local.raw["georelay"]["outside_mainland"]
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

drive =
  Repo.insert!(%Drive{
    car_id: car.id,
    start_date: date,
    start_position_id: position.id,
    end_position_id: position.id,
    start_address_id: legacy.id,
    end_address_id: local.id
  })

charging =
  Repo.insert!(%ChargingProcess{
    car_id: car.id,
    start_date: date,
    position_id: position.id,
    address_id: local.id
  })

stored_position = Repo.get!(TeslaMate.Log.Position, position.id)

for language <- ["zh-CN", "en"] do
  :ok = Locations.refresh_addresses(language)
  updated = Repo.get!(Address, local.id)
  identity = [:id, :osm_id, :osm_type, :latitude, :longitude]
  true = Map.take(updated, identity) == Map.take(local, identity)

  true =
    Map.take(updated, [:name, :display_name, :road, :house_number, :postcode]) == %{
      name: "Fixture Updated",
      display_name: "Fixture Updated Address",
      road: "Fixture Updated Road",
      house_number: "2",
      postcode: "75007"
    }

  true = updated.raw["fixture"] == "refreshed"
  true = updated.raw["georelay"] == local.raw["georelay"]
end

true = Repo.get!(Address, legacy.id) == legacy
true = Repo.get!(Drive, drive.id) == drive
true = Repo.get!(ChargingProcess, charging.id) == charging
true = Repo.get!(TeslaMate.Log.Position, position.id) == stored_position
snapshot = Repo.all(from(a in Address, order_by: a.id))
2 = length(snapshot)

for language <- ["missing", "shifted", "null-source", "wrong-source", "provider-fail"] do
  {:error, _} = Locations.refresh_addresses(language)
  true = Repo.all(from(a in Address, order_by: a.id)) == snapshot
end

{:error, _} = Locations.find_address(%{point | latitude: Decimal.new("48.8585")})
true = Repo.all(from(a in Address, order_by: a.id)) == snapshot
true = Repo.get!(Drive, drive.id) == drive
true = Repo.get!(ChargingProcess, charging.id) == charging
true = Enum.all?(snapshot, &(&1.osm_type != "unknown" and &1.display_name != "Unknown"))
concurrent_point = %{point | latitude: Decimal.new("48.858401123")}

concurrent =
  1..8
  |> Task.async_stream(fn _ -> Locations.find_address(concurrent_point) end,
    max_concurrency: 8,
    timeout: 15_000
  )
  |> Enum.map(fn {:ok, {:ok, address}} -> address end)

1 = concurrent |> Enum.map(& &1.id) |> Enum.uniq() |> length()
1 = concurrent |> Enum.map(& &1.osm_id) |> Enum.uniq() |> length()
true = Enum.all?(concurrent, &(&1.raw["osm_id"] == &1.osm_id))
3 = Repo.aggregate(Address, :count, :id)

{:ok, response} =
  Finch.build(:get, "http://stub:8080/assertions")
  |> Finch.request(TeslaMate.HTTP, receive_timeout: 5_000)

200 = response.status
%{"ok" => true} = Jason.decode!(response.body)
IO.puts("GEORELAY_RUNTIME_LOCATIONS_OK")
