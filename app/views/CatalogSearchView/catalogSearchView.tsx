import { Fragment } from "react";
import { CatalogSearch } from "../../components/CatalogSearch/catalogSearch";
import { SectionHero } from "../../components/Layout/components/AppLayout/components/Section/components/SectionHero/sectionHero";
import { BREADCRUMBS } from "./common/constants";
import { CatalogSearchSection } from "./catalogSearchView.styles";

export const CatalogSearchView = (): JSX.Element => {
  return (
    <Fragment>
      <SectionHero
        breadcrumbs={BREADCRUMBS}
        head="Catalog Search"
        subHead="Find genome assemblies using natural language with multi-turn conversation"
      />
      <CatalogSearchSection>
        <CatalogSearch />
      </CatalogSearchSection>
    </Fragment>
  );
};
