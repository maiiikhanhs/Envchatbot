"use client";

import { useEffect, useState } from "react";
import styles from "./WeatherWidget.module.css";

interface WeatherAqiData {
  temp: number;
  realFeel: number;
  humidity: number;
  uvIndex: number;
  windSpeed: number;
  weatherCode: number;
  isDay: boolean;
  city: string;
  aqi: number;
  pm25: number;
  pm10: number;
}

const HANOI_COORDS = { lat: 21.0285, lon: 105.8542, city: "Hà Nội" };

// Map WMO code to UI
const getWeatherConfig = (code: number, isDay: boolean) => {
  if (code === 0) return { text: "Trời quang mây", icon: isDay ? "☀️" : "🌙" };
  if (code === 1 || code === 2) return { text: "Ít mây", icon: isDay ? "🌤️" : "☁️" };
  if (code === 3) return { text: "Nhiều mây", icon: "☁️" };
  if (code >= 45 && code <= 48) return { text: "Sương mù", icon: "🌫️" };
  if (code >= 51 && code <= 55) return { text: "Mưa phùn", icon: "🌧️" };
  if (code >= 61 && code <= 65) return { text: "Mưa", icon: "🌧️" };
  if (code >= 71 && code <= 77) return { text: "Tuyết rơi", icon: "❄️" };
  if (code >= 80 && code <= 82) return { text: "Mưa rào", icon: "🌦️" };
  if (code >= 95 && code <= 99) return { text: "Sấm chớp", icon: "⛈️" };
  return { text: "Không rõ", icon: "🌡️" };
};

const getAqiConfig = (aqi: number) => {
  if (aqi <= 50) {
    return {
      status: "Tốt",
      color: "#10b981", // Emerald
      icon: "🟢",
    };
  }
  if (aqi <= 100) {
    return {
      status: "Trung bình",
      color: "#f59e0b", // Amber
      icon: "🟡",
    };
  }
  if (aqi <= 150) {
    return {
      status: "Kém",
      color: "#f97316", // Orange
      icon: "🟠",
    };
  }
  if (aqi <= 200) {
    return {
      status: "Xấu",
      color: "#ef4444", // Red
      icon: "🔴",
    };
  }
  if (aqi <= 300) {
    return {
      status: "Rất xấu",
      color: "#a855f7", // Purple
      icon: "🟣",
    };
  }
  return {
    status: "Nguy hại",
    color: "#7c2d12", // Deep Brown
    icon: "🟤",
  };
};

const getDayString = () => {
  const days = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
  const now = new Date();
  return {
    day: days[now.getDay()],
    date: `${now.getDate()}/${now.getMonth() + 1}`
  };
};

export default function WeatherWidget() {
  const [data, setData] = useState<WeatherAqiData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAllData() {
      try {
        // Step 1: Get IP Location
        let lat = HANOI_COORDS.lat;
        let lon = HANOI_COORDS.lon;
        let city = HANOI_COORDS.city;

        try {
          const ipRes = await fetch("https://ipapi.co/json/");
          if (ipRes.ok) {
            const ipData = await ipRes.json();
            if (ipData.latitude && ipData.longitude) {
              lat = ipData.latitude;
              lon = ipData.longitude;
              city = ipData.city || city;
            }
          }
        } catch (e) {
          console.log("IP Geolocation failed, using fallback");
        }

        // Step 2: Fetch Open-Meteo Weather & Air Quality in parallel
        const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m&daily=uv_index_max&timezone=auto`;
        const aqiUrl = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=us_aqi,pm2_5,pm10&timezone=auto`;

        const [weatherRes, aqiRes] = await Promise.all([
          fetch(weatherUrl),
          fetch(aqiUrl).catch(() => null)
        ]);

        if (!weatherRes.ok) throw new Error("Failed to fetch weather");
        const weatherData = await weatherRes.json();

        let aqi = 0;
        let pm25 = 0;
        let pm10 = 0;
        if (aqiRes && aqiRes.ok) {
          const aqiData = await aqiRes.json();
          aqi = aqiData.current.us_aqi || 0;
          pm25 = aqiData.current.pm2_5 || 0;
          pm10 = aqiData.current.pm10 || 0;
        }

        setData({
          temp: Math.round(weatherData.current.temperature_2m),
          realFeel: Math.round(weatherData.current.apparent_temperature),
          humidity: Math.round(weatherData.current.relative_humidity_2m),
          uvIndex: weatherData.daily.uv_index_max[0] || 0,
          windSpeed: Math.round(weatherData.current.wind_speed_10m),
          weatherCode: weatherData.current.weather_code,
          isDay: weatherData.current.is_day === 1,
          city: city,
          aqi,
          pm25,
          pm10
        });
      } catch (err) {
        console.error("WeatherAqiWidget error:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchAllData();

    // Auto-refresh every 30 minutes
    const intervalId = setInterval(fetchAllData, 1800000);
    return () => clearInterval(intervalId);
  }, []);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Đang cập nhật...</div>
      </div>
    );
  }

  if (!data) return null;

  const weatherConfig = getWeatherConfig(data.weatherCode, data.isDay);
  const aqiConfig = getAqiConfig(data.aqi);
  const { day, date } = getDayString();

  // SVG Gauge Math (270-degree arc with cx=50, cy=50, r=36)
  const radius = 36;
  const circumference = 2 * Math.PI * radius; // ~226.2
  const strokeDasharray = `${circumference * 0.75} ${circumference}`; // ~169.6 visible arc
  const activeLength = (Math.min(data.aqi, 300) / 300) * (circumference * 0.75);
  const strokeDashoffset = circumference * 0.75 - activeLength;

  // PM progress bars percentages
  const pm25Percent = Math.min((data.pm25 / 75) * 100, 100);
  const pm10Percent = Math.min((data.pm10 / 150) * 100, 100);

  return (
    <div className={styles.container}>
      {/* ── WEATHER PORTION ── */}
      <div className={styles.topRow}>
        <div className={styles.dateInfo}>
          <span>{day}</span>
          <span>{date}</span>
        </div>

        <div className={styles.tempSection}>
          <span className={styles.icon}>{weatherConfig.icon}</span>
          <div className={styles.tempValue}>
            <span className={styles.mainTemp}>{data.temp}°</span>
          </div>
        </div>
      </div>

      <div className={styles.cityLabel}>📍 {data.city}</div>
      <div className={styles.status}>{weatherConfig.text}</div>

      <div className={styles.divider}></div>

      <div className={styles.details}>
        <div className={styles.detailItem}>
          <span className={styles.detailLabel}>RealFeel™</span>
          <span className={styles.detailValue}>{data.realFeel}°C</span>
        </div>
        <div className={styles.detailItem}>
          <span className={styles.detailLabel}>Chỉ số UV</span>
          <span className={styles.detailValue}>{data.uvIndex}</span>
        </div>
        <div className={styles.detailItem}>
          <span className={styles.detailLabel}>Độ ẩm</span>
          <span className={styles.detailValue}>💧 {data.humidity}%</span>
        </div>
        <div className={styles.detailItem}>
          <span className={styles.detailLabel}>Gió</span>
          <span className={styles.detailValue}>💨 {data.windSpeed} km/h</span>
        </div>
      </div>

      {/* ── AIR QUALITY PORTION ── */}
      <div className={styles.divider}></div>

      <div className={styles.aqiHeader}>
        <span className={styles.aqiTitle}>Chất lượng không khí</span>
      </div>

      <div className={styles.aqiContent}>
        {/* Left Side: Circular SVG Gauge */}
        <div className={styles.gaugeContainer}>
          <svg className={styles.gauge} viewBox="0 0 100 100">
            <circle
              className={styles.gaugeTrack}
              cx="50"
              cy="50"
              r={radius}
              strokeWidth="7"
              fill="transparent"
              strokeDasharray={strokeDasharray}
            />
            <circle
              className={styles.gaugeActive}
              cx="50"
              cy="50"
              r={radius}
              strokeWidth="7"
              fill="transparent"
              stroke={aqiConfig.color}
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
            />
          </svg>
          <div className={styles.gaugeValueContainer}>
            <span className={styles.gaugeValue}>{data.aqi}</span>
            <span className={styles.gaugeLabel}>AQI</span>
          </div>
        </div>

        {/* Right Side: Status and PM details */}
        <div className={styles.aqiInfo}>
          <div className={styles.aqiStatusRow}>
            <span className={styles.aqiStatusText} style={{ color: aqiConfig.color }}>
              {aqiConfig.icon} {aqiConfig.status}
            </span>
          </div>

          <div className={styles.pmList}>
            <div className={styles.pmItem}>
              <div className={styles.pmHeader}>
                <span className={styles.pmLabel}>PM2.5</span>
                <span className={styles.pmValue}>{data.pm25} µg/m³</span>
              </div>
              <div className={styles.progressBarBg}>
                <div 
                  className={styles.progressBarActive} 
                  style={{ width: `${pm25Percent}%`, backgroundColor: aqiConfig.color }}
                />
              </div>
            </div>

            <div className={styles.pmItem}>
              <div className={styles.pmHeader}>
                <span className={styles.pmLabel}>PM10</span>
                <span className={styles.pmValue}>{data.pm10} µg/m³</span>
              </div>
              <div className={styles.progressBarBg}>
                <div 
                  className={styles.progressBarActive} 
                  style={{ width: `${pm10Percent}%`, backgroundColor: aqiConfig.color }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

