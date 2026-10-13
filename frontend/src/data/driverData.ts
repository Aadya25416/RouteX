import { DriverTrip } from "@/types/driver";

export const GUWAHATI_TAWANG_CORRIDOR_COORDS: [number, number][] = [
  [91.7362, 26.1445], // Guwahati
  [91.9500, 26.1800], // Jagiroad
  [92.6842, 26.3452], // Nagaon
  [92.7930, 26.6528], // Tezpur bridge junction
  [92.5186, 27.0135], // Bhalukpong (Assam-Arunachal border)
  [92.4820, 27.1500], // Tenga Valley
  [92.4159, 27.2645], // Bomdila (Landslide risk)
  [92.2356, 27.3577], // Dirang
  [92.1051, 27.5028], // Sela Pass
  [91.9800, 27.5400], // Jang
  [91.8687, 27.5861], // Tawang
];

export const INITIAL_DRIVER_TRIP: DriverTrip = {
  id: "TRIP-GHY-TWG-8041",
  origin: "Guwahati",
  destination: "Tawang",
  corridor: "NH-27",
  totalDistanceKm: 520,
  estimatedDuration: "12 hr 30 min",
  actualDuration: "12 hr 45 min",
  vehicleNumber: "Truck (MH 12 AB 1234)",
  vehicleType: "Heavy Freight Transport (Type B)",
  status: "IN_TRANSIT",
  hasHazardWarning: true,
  hazardDetails: {
    location: "NH-27, near Bomdila, Arunachal Pradesh",
    type: "landslide",
    severity: "HIGH",
    message: "Landslide risk reported near Bomdila (Illustrative)",
    coordinates: [92.4159, 27.2645],
  },
  stops: [
    {
      id: "stop-1",
      name: "Guwahati",
      time: "06:00 AM",
      status: "Departed",
      isCompleted: true,
      coordinates: [91.7362, 26.1445],
    },
    {
      id: "stop-2",
      name: "Nagaon",
      time: "08:30 AM",
      status: "Completed",
      isCompleted: true,
      coordinates: [92.6842, 26.3452],
    },
    {
      id: "stop-3",
      name: "Bomdila",
      time: "01:15 PM",
      status: "Next stop",
      isNext: true,
      coordinates: [92.4159, 27.2645],
    },
    {
      id: "stop-4",
      name: "Tawang",
      time: "09:00 PM",
      status: "Destination",
      isDestination: true,
      coordinates: [91.8687, 27.5861],
    },
  ],
};
