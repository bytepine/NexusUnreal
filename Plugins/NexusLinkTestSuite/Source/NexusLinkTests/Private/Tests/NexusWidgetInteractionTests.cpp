// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusReliabilityTestTypes.h"
#include "NexusCapabilityRegistry.h"
#include "Utils/NexusRuntimeUtils.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Button.h"
#include "Components/VerticalBox.h"
#include "Components/WidgetSwitcher.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/ScopeExit.h"
#include "WidgetBlueprint.h"
#include "Widgets/SOverlay.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusWidgetInteractionTest, "NexusLink.Runtime.Widget.ExactInteraction",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusWidgetInteractionTest::RunTest(const FString& Parameters)
{
	const FCapRecord* Interact = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("InteractRuntimeWidget"));
	const FCapRecord* List = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("ListRuntimeWidgets"));
	if (!TestNotNull(TEXT("Interact registered"), Interact) || !TestNotNull(TEXT("List registered"), List)) return false;
	FString WorldError;
	if (!TestNull(TEXT("Run outside an existing play session"), FNexusRuntimeUtils::RequirePlayWorld(WorldError))) return false;

	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	UGameViewportClient* Viewport = NewObject<UGameViewportClient>(GEngine);
	Context.GameViewport = Viewport;
	TSharedRef<SOverlay> Overlay = SNew(SOverlay);
    // The fixture intentionally mounts an isolated overlay without a real viewport.
    PRAGMA_DISABLE_DEPRECATION_WARNINGS
    Viewport->SetViewportOverlayWidget(nullptr, Overlay);
    PRAGMA_ENABLE_DEPRECATION_WARNINGS
	TArray<UUserWidget*> Instances;
	ON_SCOPE_EXIT
	{
		for (UUserWidget* Instance : Instances) Instance->RemoveFromParent();
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	};

	UPackage* Package = CreatePackage(*(TEXT("/Temp/NexusWidgetInteraction_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWidgetBlueprint* Blueprint = Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(UUserWidget::StaticClass(), Package,
		TEXT("Panel"), BPTYPE_Normal, UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass()));
	if (!TestNotNull(TEXT("Test blueprint"), Blueprint)) return false;
	UVerticalBox* Root = Blueprint->WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Root"));
	Blueprint->WidgetTree->RootWidget = Root;
	Root->AddChild(Blueprint->WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BackButton")));
	FKismetEditorUtilities::CompileBlueprint(Blueprint);

	auto Spawn = [&](const TCHAR* Name)
	{
		UClass* WidgetClass = Blueprint->GeneratedClass;
		UUserWidget* Instance = CreateWidget<UUserWidget>(World, WidgetClass, FName(Name));
		if (Instance) Instances.Add(Instance);
		return Instance;
	};
	// 先创建缓存实例，旧实现会在全局对象遍历中先命中它。
	UUserWidget* Cached = Spawn(TEXT("CachedPanel"));
	UUserWidget* First = Spawn(TEXT("FirstPanel"));
	UUserWidget* Second = Spawn(TEXT("SecondPanel"));
	if (!TestNotNull(TEXT("Cached panel"), Cached) || !TestNotNull(TEXT("First panel"), First)
		|| !TestNotNull(TEXT("Second panel"), Second)) return false;
	// 模拟界面缓存仍持有 Slate：移出视口后 IsVisible 依旧为真。
	const TSharedRef<SWidget> CachedSlate = Cached->TakeWidget();
	Cached->AddToViewport();
	Cached->RemoveFromParent();
	First->AddToViewport();
	Second->AddToViewport();
	if (!TestTrue(TEXT("First in viewport"), First->IsInViewport()) || !TestTrue(TEXT("Second in viewport"), Second->IsInViewport())) return false;
	TestTrue(TEXT("Cached instance remains locally visible"), CachedSlate->GetVisibility().IsVisible() && Cached->IsVisible());
	TestFalse(TEXT("Cached instance detached"), Cached->IsInViewport());
	UButton* CachedButton = Cast<UButton>(Cached->GetWidgetFromName(TEXT("BackButton")));
	UButton* FirstButton = Cast<UButton>(First->GetWidgetFromName(TEXT("BackButton")));
	UButton* SecondButton = Cast<UButton>(Second->GetWidgetFromName(TEXT("BackButton")));
	if (!TestNotNull(TEXT("Cached button"), CachedButton) || !TestNotNull(TEXT("First button"), FirstButton)
		|| !TestNotNull(TEXT("Second button"), SecondButton)) return false;
	UNexusWidgetClickRecorder* FirstClicks = NewObject<UNexusWidgetClickRecorder>(First);
	UNexusWidgetClickRecorder* SecondClicks = NewObject<UNexusWidgetClickRecorder>(Second);
	UNexusWidgetClickRecorder* CachedClicks = NewObject<UNexusWidgetClickRecorder>(Cached);
	FirstButton->OnClicked.AddDynamic(FirstClicks, &UNexusWidgetClickRecorder::RecordClick);
	SecondButton->OnClicked.AddDynamic(SecondClicks, &UNexusWidgetClickRecorder::RecordClick);
	CachedButton->OnClicked.AddDynamic(CachedClicks, &UNexusWidgetClickRecorder::RecordClick);

	auto Click = [&](const TCHAR* Locator, const FString& Value)
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetStringField(Locator, Value);
		Args->SetStringField(TEXT("Action"), TEXT("Click"));
		return Interact->Instance->Run(Args);
	};
	const FCapabilityResult Ambiguous = Click(TEXT("WidgetName"), TEXT("BackButton"));
	TestTrue(TEXT("Duplicate names rejected"), Ambiguous.HasErrors());
	if (TestEqual(TEXT("Ambiguity entry"), Ambiguous.Entries.Num(), 1))
	{
		const TArray<TSharedPtr<FJsonValue>>* Candidates = nullptr;
		if (TestTrue(TEXT("Candidate paths returned"), Ambiguous.Entries[0]->AsObject()->TryGetArrayField(TEXT("Candidates"), Candidates)))
			TestEqual(TEXT("Only mounted candidates"), Candidates->Num(), 2);
	}
	TestEqual(TEXT("No first click on ambiguity"), FirstClicks->ClickCount, 0);
	TestEqual(TEXT("No second click on ambiguity"), SecondClicks->ClickCount, 0);
	TestEqual(TEXT("No cached click on ambiguity"), CachedClicks->ClickCount, 0);

	TSharedPtr<FJsonObject> ListArgs = MakeShared<FJsonObject>();
	ListArgs->SetStringField(TEXT("NameFilter"), TEXT("BackButton"));
	const FCapabilityResult Listed = List->Instance->Run(ListArgs);
	if (!TestFalse(TEXT("List succeeds"), Listed.HasErrors()) || !TestEqual(TEXT("List entry"), Listed.Entries.Num(), 1)) return false;
	const TArray<TSharedPtr<FJsonValue>>& Widgets = Listed.Entries[0]->AsObject()->GetArrayField(TEXT("Widgets"));
	TestEqual(TEXT("List excludes cached button"), Widgets.Num(), 2);
	FString FirstPath;
	for (const TSharedPtr<FJsonValue>& Widget : Widgets)
	{
		const FString Path = Widget->AsObject()->GetStringField(TEXT("Path"));
		if (Path == FirstButton->GetPathName()) FirstPath = Path;
	}
	if (!TestFalse(TEXT("List exposes exact instance path"), FirstPath.IsEmpty())) return false;
	TestFalse(TEXT("Exact path click succeeds"), Click(TEXT("WidgetPath"), FirstPath).HasErrors());
	TestEqual(TEXT("Only first button clicked"), FirstClicks->ClickCount, 1);
	TestEqual(TEXT("Second button untouched"), SecondClicks->ClickCount, 0);
	TestTrue(TEXT("Cached path rejected"), Click(TEXT("WidgetPath"), CachedButton->GetPathName()).HasErrors());
	TestTrue(TEXT("Unknown path rejected"), Click(TEXT("WidgetPath"), FirstPath + TEXT("_missing")).HasErrors());
	TestTrue(TEXT("Empty path rejected"), Click(TEXT("WidgetPath"), TEXT("")).HasErrors());
	TSharedPtr<FJsonObject> ConflictingArgs = MakeShared<FJsonObject>();
	ConflictingArgs->SetStringField(TEXT("Action"), TEXT("Click"));
	TestTrue(TEXT("Missing locator rejected"), Interact->Instance->Run(ConflictingArgs).HasErrors());
	ConflictingArgs->SetStringField(TEXT("WidgetName"), TEXT("BackButton"));
	ConflictingArgs->SetStringField(TEXT("WidgetPath"), FirstPath + TEXT("_missing"));
	TestTrue(TEXT("Invalid explicit path never falls back to name"), Interact->Instance->Run(ConflictingArgs).HasErrors());
	ConflictingArgs->SetStringField(TEXT("WidgetPath"), FirstPath);
	ConflictingArgs->SetStringField(TEXT("OwnerClass"), TEXT("SecondPanel"));
	TestTrue(TEXT("Conflicting owner filter rejected"), Interact->Instance->Run(ConflictingArgs).HasErrors());
	TestEqual(TEXT("Cached button never clicked"), CachedClicks->ClickCount, 0);

	FirstButton->SetIsEnabled(false);
	TestTrue(TEXT("Disabled button rejected"), Click(TEXT("WidgetPath"), FirstPath).HasErrors());
	FirstButton->SetIsEnabled(true);
	First->SetVisibility(ESlateVisibility::Collapsed);
	TestTrue(TEXT("Hidden ancestor rejects exact path"), Click(TEXT("WidgetPath"), FirstPath).HasErrors());
	First->SetVisibility(ESlateVisibility::Visible);
	Second->RemoveFromParent();
	TestFalse(TEXT("Unique name ignores detached instance"), Click(TEXT("WidgetName"), TEXT("BackButton")).HasErrors());
	TestEqual(TEXT("Unique name hits first"), FirstClicks->ClickCount, 2);
	TestTrue(TEXT("Detached exact path rejected"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());

	// 嵌套面板本身不在视口根列表，必须沿活动层级进入；移除后不能仅按 Outer 误判。
	UVerticalBox* FirstRoot = Cast<UVerticalBox>(First->WidgetTree->RootWidget);
	FirstRoot->AddChild(Second);
	const FCapabilityResult NestedList = List->Instance->Run(ListArgs);
	if (!TestFalse(TEXT("Nested list succeeds"), NestedList.HasErrors()) || !TestEqual(TEXT("Nested list entry"), NestedList.Entries.Num(), 1)) return false;
	TestEqual(TEXT("List discovers nested button"), NestedList.Entries[0]->AsObject()->GetArrayField(TEXT("Widgets")).Num(), 2);
	TestTrue(TEXT("Nested duplicate names rejected"), Click(TEXT("WidgetName"), TEXT("BackButton")).HasErrors());
	TestFalse(TEXT("Nested exact path works"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());
	TestEqual(TEXT("Nested button clicked once"), SecondClicks->ClickCount, 1);
	Second->SetVisibility(ESlateVisibility::Hidden);
	TestTrue(TEXT("Hidden nested ancestor rejected"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());
	Second->SetVisibility(ESlateVisibility::Visible);
	Second->RemoveFromParent();
	TestTrue(TEXT("Removed nested path rejected"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());
	UWidgetSwitcher* Switcher = First->WidgetTree->ConstructWidget<UWidgetSwitcher>();
	FirstRoot->AddChild(Switcher);
	Switcher->AddChild(First->WidgetTree->ConstructWidget<UButton>());
	Switcher->AddChild(Second);
	Switcher->SetActiveWidgetIndex(0);
	TestTrue(TEXT("Inactive switcher page rejected"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());
	Switcher->SetActiveWidgetIndex(1);
	TestFalse(TEXT("Active switcher page accepted"), Click(TEXT("WidgetPath"), SecondButton->GetPathName()).HasErrors());
	TestEqual(TEXT("Only active nested page clicked"), SecondClicks->ClickCount, 2);
	TestEqual(TEXT("Cached button still untouched"), CachedClicks->ClickCount, 0);
	return true;
}
#endif
