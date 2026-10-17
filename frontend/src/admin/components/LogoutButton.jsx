export default function LogoutButton({ onLogout }) {
  return (
    <button
      onClick={onLogout}
      style={{ float: "right" }}
    >
      Logout
    </button>
  );
}
