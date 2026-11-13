// Copyright byteyang. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "Utils/NexusVersionCompat.h"

#if WITH_EDITOR && WITH_NEXUS_TEST_PCG_DOCUMENTS && NX_UE_HAS_PCG_EDITOR_DOCUMENT_TABS
#include "AssetRegistry/AssetRegistryModule.h"
#include "Editor.h"
#include "Elements/PCGDensityFilter.h"
#include "Framework/Application/SlateApplication.h"
#include "PCGEditor.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusPCGGraphDocumentFixtureTest,
	"NexusLink.EditorGraph.PCGMultiDocumentFixture",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusPCGGraphDocumentFixtureTest::RunTest(const FString& Parameters)
{
	if (IsRunningCommandlet() || !FSlateApplication::IsInitialized())
	{
		AddInfo(TEXT("PCG 多文档夹具需要 GUI 编辑器"));
		return true;
	}
	if (!TestNotNull(TEXT("Editor host"), GEditor)) return false;
	auto* Editors = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!TestNotNull(TEXT("Asset editor subsystem"), Editors)) return false;

	const FString PackagePath = TEXT("/Game/_McpTest/PCGGraphDocuments_") + FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT("/PCG_DocumentFixture");
	UPackage* Package = CreatePackage(*PackagePath);
	UPCGGraph* RootGraph = NewObject<UPCGGraph>(Package, TEXT("PCG_DocumentFixture"), RF_Public | RF_Standalone | RF_Transactional);
	FAssetRegistryModule::AssetCreated(RootGraph);
	UPCGGraph* FirstGraph = RootGraph->AddNewEmbeddedSubgraph();
	UPCGGraph* SecondGraph = RootGraph->AddNewEmbeddedSubgraph();
	if (!TestNotNull(TEXT("First embedded graph"), FirstGraph) || !TestNotNull(TEXT("Second embedded graph"), SecondGraph)) return false;
	FirstGraph->Rename(TEXT("GraphA"), RootGraph, REN_DontCreateRedirectors);
	SecondGraph->Rename(TEXT("GraphB"), RootGraph, REN_DontCreateRedirectors);
	if (!TestNotNull(TEXT("First input node"), FirstGraph->GetInputNode())
		|| !TestNotNull(TEXT("Second input node"), SecondGraph->GetInputNode())) return false;
	FirstGraph->GetInputNode()->SetNodePosition(64, 96);
	SecondGraph->GetInputNode()->SetNodePosition(400, 192);
	for (UPCGGraph* Graph : {RootGraph, FirstGraph, SecondGraph})
	{
		UPCGDensityFilterSettings* Settings = nullptr;
		UPCGNode* Probe = Graph->AddNodeOfType(Settings);
		if (!TestNotNull(TEXT("Document probe node"), Probe)) return false;
		// 编辑图 GUID 按 PCGNode 名称生成；内建节点及各图默认节点名都会重复。
		const FString ProbeName = TEXT("GraphDocumentProbe_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
		if (!TestTrue(TEXT("Unique probe object name"), Probe->Rename(*ProbeName, Graph, REN_DontCreateRedirectors))) return false;
		if (!TestTrue(TEXT("Discoverable probe title"), Probe->SetNodeTitle(FName(TEXT("GraphDocumentProbe"))))) return false;
	}

	if (!TestTrue(TEXT("Open root PCG editor"), Editors->OpenEditorForAsset(RootGraph))) return false;
	IAssetEditorInstance* AssetEditor = Editors->FindEditorForAsset(RootGraph, false);
	if (!TestTrue(TEXT("Owned PCG editor"), AssetEditor && AssetEditor->GetEditorName() == FName(TEXT("PCGEditor")))) return false;
	auto* PCGEditor = static_cast<FPCGEditor*>(AssetEditor);
	if (!TestNotNull(TEXT("First closed graph document"), PCGEditor->GetOrCreatePCGEditorGraph(FirstGraph))
		|| !TestNotNull(TEXT("Second closed graph document"), PCGEditor->GetOrCreatePCGEditorGraph(SecondGraph))) return false;

	// 只预建图数据，不打开子图文档或落盘；MCP 关闭编辑器后由会话清理回收。
	Package->SetDirtyFlag(false);
	return true;
}
#endif
