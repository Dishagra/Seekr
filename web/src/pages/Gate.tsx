import { useState } from "react";
import { useAuth } from "../context/auth";
import { Icon } from "../lib/icons";
import { Mark } from "../lib/mark";

export function Gate() {
  const { signIn } = useAuth();
  const [value, setValue] = useState("");
  // The token is masked by default — it is a credential, and people paste it
  // with someone watching. The eye is for checking a paste actually landed.
  const [visible, setVisible] = useState(false);

  const submit = () => {
    if (value.trim()) signIn(value);
  };

  return (
    <div className="gate">
      <div className="gatebox">
        <div className="mark">
          <Mark size={15} />
        </div>
        <h1>Sign in to Seekr</h1>
        <p>Paste the API token (RIP_API_TOKEN). It is stored only in this browser.</p>
        <div className="secretfield">
          <input
            id="tok"
            type={visible ? "text" : "password"}
            placeholder="Token"
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="off"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
          />
          <button
            type="button"
            className="reveal"
            aria-pressed={visible}
            aria-label={visible ? "Hide token" : "Show token"}
            title={visible ? "Hide token" : "Show token"}
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? <Icon.eyeOff /> : <Icon.eye />}
          </button>
        </div>
        <button className="btn primary" onClick={submit}>
          Continue
        </button>
      </div>
    </div>
  );
}
