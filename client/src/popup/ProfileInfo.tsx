import { useState } from "react";

interface ProfileInfoProps {
  onSave: (info: Record<string, string>) => void;
}

export default function ProfileInfo({ onSave }: ProfileInfoProps) {
  const [name, setName] = useState("");
  const [experience, setExperience] = useState("");
  const [skills, setSkills] = useState("");

  const handleSave = () => {
    onSave({ name, experience, skills });
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <label
        style={{
          display: "block",
          fontSize: "0.85rem",
          marginBottom: 4,
          fontWeight: 500,
        }}
      >
        👤 Profile Info (Optional)
      </label>
      <input
        type="text"
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={handleSave}
        style={{
          width: "100%",
          marginBottom: 4,
          fontSize: "0.8rem",
          padding: 4,
          border: "1px solid #ccc",
          borderRadius: 4,
        }}
      />
      <input
        type="text"
        placeholder="Years of Experience"
        value={experience}
        onChange={(e) => setExperience(e.target.value)}
        onBlur={handleSave}
        style={{
          width: "100%",
          marginBottom: 4,
          fontSize: "0.8rem",
          padding: 4,
          border: "1px solid #ccc",
          borderRadius: 4,
        }}
      />
      <input
        type="text"
        placeholder="Key Skills (comma-separated)"
        value={skills}
        onChange={(e) => setSkills(e.target.value)}
        onBlur={handleSave}
        style={{
          width: "100%",
          fontSize: "0.8rem",
          padding: 4,
          border: "1px solid #ccc",
          borderRadius: 4,
        }}
      />
    </div>
  );
}

