import { GetStaticProps } from "next";
import { StyledPagesMain } from "../../app/components/Layout/components/Main/main.styles";
import { CatalogSearchView } from "../../app/views/CatalogSearchView/catalogSearchView";

export const CatalogSearch = (): JSX.Element => {
  return <CatalogSearchView />;
};

export const getStaticProps: GetStaticProps = async () => {
  return {
    props: {
      pageTitle: "Catalog Search",
      themeOptions: {
        palette: { background: { default: "#FAFBFB" } }, // SMOKE_LIGHTEST
      },
    },
  };
};

export default CatalogSearch;

CatalogSearch.Main = StyledPagesMain;
