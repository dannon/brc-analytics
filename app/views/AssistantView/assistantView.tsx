import { Fragment, JSX } from "react";
import { useFeatureFlag } from "@databiosphere/findable-ui/lib/hooks/useFeatureFlag/useFeatureFlag";
import Error from "next/error";
import { SectionHero } from "../../components/Layout/components/AppLayout/components/Section/components/SectionHero/sectionHero";
import { ChatPanel, SchemaPanel } from "../../components/Assistant";
import { useAssistantChat } from "../../hooks/useAssistantChat";
import { BREADCRUMBS } from "./common/constants";
import {
  AssistantSection,
  ChatColumn,
  SchemaColumn,
  TwoPanelLayout,
} from "./assistantView.styles";

interface Props {
  initialSavedAnalysisId?: string;
  initialSessionId?: string;
}

export const AssistantView = ({
  initialSavedAnalysisId,
  initialSessionId,
}: Props): JSX.Element => {
  const isAssistantEnabled = useFeatureFlag("assistant");
  const {
    error,
    handoffUrl,
    loading,
    messages,
    saveAnalysis,
    saveLoading,
    saveMessage,
    schema,
    sendMessage,
    suggestions,
  } = useAssistantChat({
    initialSavedAnalysisId,
    initialSessionId,
  });

  if (!isAssistantEnabled) return <Error statusCode={404} />;

  return (
    <Fragment>
      <SectionHero
        breadcrumbs={BREADCRUMBS}
        head="Analysis Assistant"
        subHead="Explore data and configure analyses with AI guidance"
      />
      <AssistantSection>
        <TwoPanelLayout>
          <ChatColumn>
            <ChatPanel
              error={error}
              loading={loading}
              messages={messages}
              onSave={saveAnalysis}
              onSend={sendMessage}
              saveLabel={saveMessage}
              saveLoading={saveLoading}
              suggestions={suggestions}
            />
          </ChatColumn>
          <SchemaColumn>
            <SchemaPanel handoffUrl={handoffUrl} schema={schema} />
          </SchemaColumn>
        </TwoPanelLayout>
      </AssistantSection>
    </Fragment>
  );
};
