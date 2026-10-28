export default function EmBreve({ titulo, fase }: { titulo: string; fase: string }) {
  return (
    <>
      <header className="cabecalho">
        <h1>{titulo}</h1>
        <p>Esta tela entra na {fase} do projeto.</p>
      </header>
    </>
  );
}
