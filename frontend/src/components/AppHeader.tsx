export type AppHeaderProps = {
  productName: string;
  subtitle: string;
};

export default function AppHeader({ productName, subtitle }: AppHeaderProps) {
  return (
    <header>
      <h1>{productName}</h1>
      <p>{subtitle}</p>
    </header>
  );
}
