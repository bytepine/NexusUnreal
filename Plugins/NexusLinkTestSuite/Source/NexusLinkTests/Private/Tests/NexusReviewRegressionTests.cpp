// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "Server/NexusMcpServer.h"
#include "Async/TaskGraphInterfaces.h"
#include "Utils/NexusVersionCompat.h"
#include "Utils/NexusJsonUtils.h"
#include "Components/SceneComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/Engine.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Editor.h"
#include "FileHelpers.h"
#include "Misc/ScopeExit.h"
#include "ScopedTransaction.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/UObjectGlobals.h"

static FCapabilityResult ReviewCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Capability missing"));
}

static UBlueprint* ReviewBlueprint(UClass* ParentClass)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Review_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	return FKismetEditorUtilities::CreateBlueprint(ParentClass, Package, TEXT("Blueprint"),
		BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewScsTest, "NexusLink.Review.ScsReattachAndCopy",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewScsTest::RunTest(const FString& Parameters)
{
	UBlueprint* Parent = ReviewBlueprint(ACharacter::StaticClass());
	if (!TestNotNull(TEXT("Parent blueprint"), Parent)) return false;
	USCS_Node* Inherited = Parent->SimpleConstructionScript->CreateNode(USceneComponent::StaticClass(), TEXT("InheritedPart"));
	Parent->SimpleConstructionScript->AddNode(Inherited);
	CastChecked<USceneComponent>(Inherited->ComponentTemplate)->SetRelativeLocation(FVector(10, 20, 30));
	FKismetEditorUtilities::CompileBlueprint(Parent);
	UBlueprint* Child = ReviewBlueprint(Parent->GeneratedClass);
	if (!TestNotNull(TEXT("Child blueprint"), Child)) return false;
	USimpleConstructionScript* SCS = Child->SimpleConstructionScript;
	USCS_Node* First = SCS->CreateNode(USceneComponent::StaticClass(), TEXT("FirstPart"));
	SCS->AddNode(First);
	USCS_Node* Second = SCS->CreateNode(USceneComponent::StaticClass(), TEXT("SecondPart"));
	First->AddChildNode(Second);
	FKismetEditorUtilities::CompileBlueprint(Child);
	auto Reattach = [&](const TCHAR* Name, const TCHAR* Target)
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetStringField(TEXT("AssetPath"), Child->GetPathName());
		TSharedPtr<FJsonObject> Op = MakeShared<FJsonObject>();
		Op->SetStringField(TEXT("Action"), TEXT("ReattachComponent"));
		Op->SetStringField(TEXT("ComponentName"), Name);
		Op->SetStringField(TEXT("AttachTo"), Target);
		Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Op)});
		return ReviewCall(TEXT("ManageAssetBlueprint"), Args);
	};
	TestTrue(TEXT("Self attachment rejected"), Reattach(TEXT("FirstPart"), TEXT("FirstPart")).HasErrors());
	TestTrue(TEXT("Descendant attachment rejected"), Reattach(TEXT("FirstPart"), TEXT("SecondPart")).HasErrors());
	TestTrue(TEXT("Rejected cycle preserves tree"), First->GetChildNodes().Contains(Second));
	const int32 NodeCount = SCS->GetAllNodes().Num();
	TestFalse(TEXT("Child to native parent"), Reattach(TEXT("SecondPart"), *ACharacter::CapsuleComponentName.ToString()).HasErrors());
	TestTrue(TEXT("Native attachment becomes SCS root"), SCS->GetRootNodes().Contains(Second));
	TestFalse(TEXT("Old parent detached"), First->GetChildNodes().Contains(Second));
	TestEqual(TEXT("AllNodes unchanged"), SCS->GetAllNodes().Num(), NodeCount);
	TestFalse(TEXT("Root to local parent"), Reattach(TEXT("SecondPart"), TEXT("FirstPart")).HasErrors());
	TestFalse(TEXT("Local child removed from roots"), SCS->GetRootNodes().Contains(Second));
	TestTrue(TEXT("Local attachment restored"), First->GetChildNodes().Contains(Second));
	TestEqual(TEXT("No duplicate AllNodes"), SCS->GetAllNodes().Num(), NodeCount);
	TestFalse(TEXT("Local child to inherited parent"), Reattach(TEXT("SecondPart"), TEXT("InheritedPart")).HasErrors());
	TestTrue(TEXT("Inherited attachment becomes root"), SCS->GetRootNodes().Contains(Second));

	UActorComponent* Override = Child->GetInheritableComponentHandler(true)->CreateOverridenComponentTemplate(FComponentKey(Inherited));
	USceneComponent* SceneOverride = Cast<USceneComponent>(Override);
	if (!TestNotNull(TEXT("Inherited override"), SceneOverride)) return false;
	const FVector OverrideLocation(111, 222, 333);
	SceneOverride->SetRelativeLocation(OverrideLocation);
	FKismetEditorUtilities::CompileBlueprint(Child);
	CastChecked<ACharacter>(Child->GeneratedClass->GetDefaultObject())->GetCapsuleComponent()->SetCapsuleSize(80, 120);
	auto ReadArgs = MakeShared<FJsonObject>();
	ReadArgs->SetStringField(TEXT("AssetPath"), Child->GetPathName());
	ReadArgs->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Component"))});
	const FCapabilityResult Components = ReviewCall(TEXT("GetAssetBlueprint"), ReadArgs);
	TestFalse(TEXT("Read inherited/native component overrides"), Components.HasErrors());
	bool bFoundNative = false, bFoundInherited = false;
	if (Components.Entries.Num() > 0)
	{
		for (const auto& Value : Components.Entries[0]->AsObject()->GetArrayField(TEXT("Components")))
		{
			const auto Component = Value->AsObject();
			const FString Name = Component->GetStringField(TEXT("VariableName"));
			if (Name == ACharacter::CapsuleComponentName.ToString())
			{
				bFoundNative = true;
				TestEqual(TEXT("Native override radius"), FCString::Atod(*Component->GetObjectField(TEXT("TemplateProperties"))->GetStringField(TEXT("CapsuleRadius"))), 80.0);
				TestTrue(TEXT("Native override resolved"), Component->GetBoolField(TEXT("bOverridesResolved")));
			}
			if (Name == TEXT("InheritedPart"))
			{
				bFoundInherited = true;
				TestTrue(TEXT("Inherited override template is target child"), Component->GetStringField(TEXT("TemplatePath")) == SceneOverride->GetPathName());
			}
		}
	}
	TestTrue(TEXT("Native component returned"), bFoundNative);
	TestTrue(TEXT("Inherited component returned"), bFoundInherited);
	UBlueprint* Dest = ReviewBlueprint(AActor::StaticClass());
	if (!TestNotNull(TEXT("Destination blueprint"), Dest)) return false;
	TSharedPtr<FJsonObject> CopyArgs = MakeShared<FJsonObject>();
	CopyArgs->SetStringField(TEXT("AssetPath"), Dest->GetPathName());
	TSharedPtr<FJsonObject> Copy = MakeShared<FJsonObject>();
	Copy->SetStringField(TEXT("Action"), TEXT("CopyComponent"));
	Copy->SetStringField(TEXT("SourceAssetPath"), Child->GetPathName());
	Copy->SetStringField(TEXT("SourceComponentName"), TEXT("InheritedPart"));
	Copy->SetStringField(TEXT("ComponentName"), TEXT("CopiedPart"));
	CopyArgs->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Copy)});
	TestFalse(TEXT("Copy inherited component"), ReviewCall(TEXT("ManageAssetBlueprint"), CopyArgs).HasErrors());
	USCS_Node* Copied = Dest->SimpleConstructionScript->FindSCSNode(TEXT("CopiedPart"));
	if (TestNotNull(TEXT("Copied node"), Copied))
	{
		TestTrue(TEXT("Child override copied"), CastChecked<USceneComponent>(Copied->ComponentTemplate)->GetRelativeLocation().Equals(OverrideLocation));
	}
	for (UBlueprint* Blueprint : {Parent, Child, Dest}) Blueprint->GetOutermost()->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackVariableTest, "NexusLink.Review.FeedbackVariableTypesAndRename",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackVariableTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Parent(ReviewBlueprint(AActor::StaticClass()));
	if (!TestNotNull(TEXT("Parent"), Parent.Get())) return false;
	ON_SCOPE_EXIT { Parent->GetOutermost()->SetDirtyFlag(false); };
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Parent->GetPathName());
	Args->SetBoolField(TEXT("bCompile"), true);
	auto Add = MakeShared<FJsonObject>();
	Add->SetStringField(TEXT("Action"), TEXT("AddVariable"));
	Add->SetStringField(TEXT("VariableName"), TEXT("OldCount"));
	Add->SetStringField(TEXT("VariableType"), TEXT("int"));
	Add->SetStringField(TEXT("DefaultValue"), TEXT("7"));
	auto Array = MakeShared<FJsonObject>();
	Array->SetStringField(TEXT("Action"), TEXT("AddVariable"));
	Array->SetStringField(TEXT("VariableName"), TEXT("Points"));
	Array->SetStringField(TEXT("VariableType"), TEXT("/Script/CoreUObject.Vector[]"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Add), MakeShared<FJsonValueObject>(Array)});
	if (!TestFalse(TEXT("Typed variables compile"), ReviewCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	const FGuid VariableGuid = Parent->NewVariables[0].VarGuid;
	auto Rename = MakeShared<FJsonObject>();
	Rename->SetStringField(TEXT("Action"), TEXT("RenameVariable"));
	Rename->SetStringField(TEXT("VariableName"), TEXT("OldCount"));
	Rename->SetStringField(TEXT("NewVariableName"), TEXT("RenamedCount"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Rename)});
	TestFalse(TEXT("Native leaf member rename"), ReviewCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Rename preserves variable GUID"), Parent->NewVariables[0].VarGuid == VariableGuid);
	TStrongObjectPtr<UBlueprint> Child(ReviewBlueprint(Parent->GeneratedClass));
	if (!TestNotNull(TEXT("Child"), Child.Get())) return false;
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	FIntProperty* OldProperty = FindFProperty<FIntProperty>(Child->GeneratedClass, TEXT("RenamedCount"));
	if (!TestNotNull(TEXT("Child property"), OldProperty)) return false;
	OldProperty->SetPropertyValue_InContainer(Child->GeneratedClass->GetDefaultObject(), 42);
	FBlueprintEditorUtils::MarkBlueprintAsModified(Child.Get());
	FKismetEditorUtilities::CompileBlueprint(Child.Get());
	OldProperty = FindFProperty<FIntProperty>(Child->GeneratedClass, TEXT("RenamedCount"));
	if (!TestNotNull(TEXT("Compiled child property"), OldProperty)) return false;
	TestEqual(TEXT("Child override exists before rename"), OldProperty->GetPropertyValue_InContainer(Child->GeneratedClass->GetDefaultObject()), 42);
	Rename->SetStringField(TEXT("VariableName"), TEXT("RenamedCount"));
	Rename->SetStringField(TEXT("NewVariableName"), TEXT("FinalCount"));
	TestTrue(TEXT("Rename with descendants rejected before modification"), ReviewCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Parent variable name unchanged"), Parent->NewVariables[0].VarName == FName(TEXT("RenamedCount")));
	FKismetEditorUtilities::CompileBlueprint(Child.Get());
	FIntProperty* Renamed = FindFProperty<FIntProperty>(Child->GeneratedClass, TEXT("RenamedCount"));
	if (TestNotNull(TEXT("Renamed child property"), Renamed))
		TestEqual(TEXT("Rejected rename preserves child default override"), Renamed->GetPropertyValue_InContainer(Child->GeneratedClass->GetDefaultObject()), 42);
	Rename->SetStringField(TEXT("VariableName"), TEXT("RenamedCount"));
	Rename->SetStringField(TEXT("NewVariableName"), TEXT("Points"));
	TestTrue(TEXT("Duplicate variable name rejected"), ReviewCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackLevelPropertyTest, "NexusLink.Review.FeedbackLevelActorProperties",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackLevelPropertyTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/ReadLevel_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("ReadLevel"), Package);
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); World->DestroyWorld(false); };
	AActor* Actor = World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Level actor"), Actor)) return false;
	Actor->SetCanBeDamaged(false);
	Package->SetDirtyFlag(false);
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), World->GetPathName());
	Args->SetStringField(TEXT("ActorName"), Actor->GetName());
	Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("ActorProperties"))});
	Args->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("bCanBeDamaged"))});
	const FCapabilityResult Result = ReviewCall(TEXT("GetAssetLevel"), Args);
	if (!TestFalse(TEXT("Level property read"), Result.HasErrors()))
	{
		AddInfo(Result.FatalError);
		for (const auto& Entry : Result.Entries) AddInfo(FNexusJsonUtils::SerializeCondensed(Entry->AsObject()));
		return false;
	}
	const auto Property = Result.Entries[0]->AsObject()->GetArrayField(TEXT("Properties"))[0]->AsObject();
	TestEqual(TEXT("Actor property value"), Property->GetStringField(TEXT("Value")), FString(TEXT("False")));
	TestEqual(TEXT("Class default value"), Property->GetStringField(TEXT("DefaultValue")), FString(TEXT("True")));
	TestTrue(TEXT("Difference from CDO"), Property->GetBoolField(TEXT("bDiffersFromDefault")));
	TestFalse(TEXT("Read preserves dirty flag"), Package->IsDirty());
	Args->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("MissingProperty"))});
	TestTrue(TEXT("Invalid property reports a section error"), ReviewCall(TEXT("GetAssetLevel"), Args).HasErrors());
	return true;
}

#if NEXUSLINK_WITH_SERVER
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFrameRequestDispatchTest, "NexusLink.Review.FrameRequestDispatch",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFrameRequestDispatchTest::RunTest(const FString& Parameters)
{
	auto Server = MakeShared<FNexusMcpServer>();
	Server->bRunning = true;
	ON_SCOPE_EXIT { Server->bRunning = false; };
	const TWeakPtr<FNexusMcpServer> WeakServer = Server;
	int32 ExecutionCount = 0;
	FNexusMcpServer::QueueRequest(WeakServer, [&]()
	{
		++ExecutionCount;
		FNexusMcpServer::QueueRequest(WeakServer, [&]() { ++ExecutionCount; });
		// 模拟编译/渲染等待处理 TaskGraph，新请求不得重入本次派发。
		FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
		TestEqual(TEXT("等待期间不重入新请求"), ExecutionCount, 1);
	});
	FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
	TestEqual(TEXT("TaskGraph 只入队，不执行请求"), ExecutionCount, 0);
	Server->ProcessPendingRequests();
	TestEqual(TEXT("首帧只执行队列快照"), ExecutionCount, 1);
	Server->ProcessPendingRequests();
	TestEqual(TEXT("下一帧处理等待期间收到的请求"), ExecutionCount, 2);
	bool bRejectedStoppedRequest = false;
	FNexusMcpServer::QueueRequest(WeakServer, [&]() { bRejectedStoppedRequest = !Server->IsRunning(); });
	FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
	Server->bRunning = false;
	Server->ProcessPendingRequests();
	TestTrue(TEXT("停止后挂起请求观察到停止状态"), bRejectedStoppedRequest);
	bool bRejectedExpiredRequest = false;
	FNexusMcpServer::QueueRequest(TWeakPtr<FNexusMcpServer>(), [&]() { bRejectedExpiredRequest = true; });
	FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);
	TestTrue(TEXT("失效服务器仍完成请求拒绝回调"), bRejectedExpiredRequest);
	return true;
}
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusComponentBatchCompileTest, "NexusLink.Review.ComponentBatchCompile",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusComponentBatchCompileTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(ReviewBlueprint(AActor::StaticClass()));
	if (!TestNotNull(TEXT("测试蓝图"), Blueprint.Get())) return false;
	int32 GarbageCollectCount = 0;
	bool bCollectedDuringTransaction = false;
	const FDelegateHandle GarbageCollectHandle = FCoreUObjectDelegates::GetPreGarbageCollectDelegate().AddLambda([&]()
	{
		++GarbageCollectCount;
		bCollectedDuringTransaction |= GEditor->IsTransactionActive();
	});
	ON_SCOPE_EXIT
	{
		FCoreUObjectDelegates::GetPreGarbageCollectDelegate().Remove(GarbageCollectHandle);
		Blueprint->GetOutermost()->SetDirtyFlag(false);
	};
	TArray<TSharedPtr<FJsonValue>> Operations;
	auto ComponentOperation = [&](const TCHAR* Action, const TCHAR* Name)
	{
		auto Operation = MakeShared<FJsonObject>();
		Operation->SetStringField(TEXT("Action"), Action);
		Operation->SetStringField(TEXT("ComponentName"), Name);
		Operations.Add(MakeShared<FJsonValueObject>(Operation));
		return Operation;
	};
	for (const TCHAR* Name : {TEXT("BatchRoot"), TEXT("BatchBody"), TEXT("BatchRemoved")})
	{
		auto Operation = ComponentOperation(TEXT("AddComponent"), Name);
		Operation->SetStringField(TEXT("ComponentClass"), TEXT("SceneComponent"));
	}
	ComponentOperation(TEXT("ReattachComponent"), TEXT("BatchBody"))->SetStringField(TEXT("AttachTo"), TEXT("BatchRoot"));
	auto Property = ComponentOperation(TEXT("SetComponentProperty"), TEXT("BatchBody"));
	Property->SetStringField(TEXT("PropertyPath"), TEXT("RelativeLocation"));
	Property->SetStringField(TEXT("Value"), TEXT("(X=1,Y=2,Z=3)"));
	ComponentOperation(TEXT("RemoveComponent"), TEXT("BatchRemoved"));
	auto Copy = ComponentOperation(TEXT("CopyComponent"), TEXT("BatchCopy"));
	Copy->SetStringField(TEXT("SourceAssetPath"), Blueprint->GetPathName());
	Copy->SetStringField(TEXT("SourceComponentName"), TEXT("BatchBody"));
	auto Defaults = MakeShared<FJsonObject>();
	Defaults->SetStringField(TEXT("Action"), TEXT("SetDefaults"));
	Defaults->SetStringField(TEXT("PropertyPath"), TEXT("bCanBeDamaged"));
	Defaults->SetStringField(TEXT("Value"), TEXT("false"));
	Operations.Add(MakeShared<FJsonValueObject>(Defaults));
	auto Function = MakeShared<FJsonObject>();
	Function->SetStringField(TEXT("Action"), TEXT("AddFunction"));
	Function->SetStringField(TEXT("FunctionName"), TEXT("ReadDamageFlag"));
	Operations.Add(MakeShared<FJsonValueObject>(Function));
	auto Node = MakeShared<FJsonObject>();
	Node->SetStringField(TEXT("Action"), TEXT("AddNode"));
	Node->SetStringField(TEXT("GraphName"), TEXT("ReadDamageFlag"));
	Node->SetStringField(TEXT("NodeClass"), TEXT("K2Node_VariableGet"));
	Node->SetStringField(TEXT("VariableName"), TEXT("bCanBeDamaged"));
	Operations.Add(MakeShared<FJsonValueObject>(Node));
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	Args->SetBoolField(TEXT("bCompile"), true);
	Args->SetArrayField(TEXT("Operations"), Operations);
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("ManageAssetBlueprint"));
	if (!TestNotNull(TEXT("蓝图编辑能力"), Record)) return false;
	FCapabilityResult Result = Record->Instance->Run(Args, false);
	TestFalse(TEXT("批量组件操作成功"), Result.HasErrors());
	TestEqual(TEXT("组件操作阶段不触发 GC"), GarbageCollectCount, 0);
	Record->Instance->Finalize(Args, Result);
	TestFalse(TEXT("集中编译成功"), Result.HasErrors());
	TestEqual(TEXT("单次收尾只触发一次 GC"), GarbageCollectCount, 1);
	TestFalse(TEXT("GC 位于事务之外"), bCollectedDuringTransaction);
	USimpleConstructionScript* Script = Blueprint->SimpleConstructionScript;
	TestNull(TEXT("组件已移除"), Script->FindSCSNode(TEXT("BatchRemoved")));
	TestNotNull(TEXT("组件已复制"), Script->FindSCSNode(TEXT("BatchCopy")));
	USCS_Node* Root = Script->FindSCSNode(TEXT("BatchRoot"));
	USCS_Node* Body = Script->FindSCSNode(TEXT("BatchBody"));
	if (TestNotNull(TEXT("根组件"), Root) && TestNotNull(TEXT("子组件"), Body))
	{
		TestTrue(TEXT("挂接关系保留"), Root->GetChildNodes().Contains(Body));
		TestTrue(TEXT("组件属性保留"), CastChecked<USceneComponent>(Body->ComponentTemplate)->GetRelativeLocation().Equals(FVector(1, 2, 3)));
	}
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Property)});
	Args->SetBoolField(TEXT("bCompile"), false);
	GarbageCollectCount = 0;
	TestFalse(TEXT("不编译的组件编辑成功"), Record->Instance->Run(Args).HasErrors());
	TestEqual(TEXT("bCompile=false 不隐式完整编译"), GarbageCollectCount, 0);
	{
		FScopedTransaction Transaction(NSLOCTEXT("NexusLinkTests", "ComponentBatch", "Component batch"));
		Args->SetBoolField(TEXT("bCompile"), true);
		TestFalse(TEXT("外层事务内编译成功"), Record->Instance->Run(Args).HasErrors());
		TestEqual(TEXT("外层事务仍活动时跳过 GC"), GarbageCollectCount, 0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewTransformTest, "NexusLink.Review.TransformValidation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewTransformTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	AActor* Actor = World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Actor"), Actor)) return false;
	USceneComponent* Root = NewObject<USceneComponent>(Actor);
	Actor->SetRootComponent(Root);
	Root->RegisterComponent();
	Actor->SetActorLocation(FVector(7, 8, 9));
	const FTransform Before = Actor->GetActorTransform();
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("ActorName"), Actor->GetName());
	Args->SetStringField(TEXT("Location"), TEXT("100,200,300"));
	Args->SetStringField(TEXT("Rotation"), TEXT("bad"));
	TestTrue(TEXT("Malformed rotation rejected"), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
	TestTrue(TEXT("Rotation failure leaves complete transform unchanged"), Actor->GetActorTransform().Equals(Before));
	Args->SetStringField(TEXT("Rotation"), TEXT("0,90,0"));
	Args->SetStringField(TEXT("Scale"), TEXT("1,2"));
	TestTrue(TEXT("Malformed scale rejected"), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
	TestTrue(TEXT("Scale failure leaves complete transform unchanged"), Actor->GetActorTransform().Equals(Before));
	Args->RemoveField(TEXT("Rotation"));
	Args->RemoveField(TEXT("Scale"));
	for (const TCHAR* Invalid : {TEXT("abc,0,0"), TEXT("1x,2,3"), TEXT("nan,0,0"), TEXT("inf,0,0"), TEXT("1e80,0,0"), TEXT("1,,2,3")})
	{
		Args->SetStringField(TEXT("Location"), Invalid);
		TestTrue(FString::Printf(TEXT("Reject %s"), Invalid), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
		TestTrue(TEXT("Invalid numbers never move Actor"), Actor->GetActorTransform().Equals(Before));
	}
	Args->SetStringField(TEXT("Location"), TEXT("1e2, -2.5, 3"));
	Args->SetStringField(TEXT("Rotation"), TEXT("0 90 0"));
	Args->SetStringField(TEXT("Scale"), TEXT("2,2,2"));
	const FCapabilityResult Changed = ReviewCall(TEXT("SetRuntimeActorTransform"), Args);
	TestFalse(TEXT("Valid transform succeeds"), Changed.HasErrors());
	TestTrue(TEXT("Location applied"), Actor->GetActorLocation().Equals(FVector(100, -2.5, 3)));
	TestTrue(TEXT("Rotation applied"), Actor->GetActorRotation().Equals(FRotator(0, 90, 0)));
	TestTrue(TEXT("Scale applied"), Actor->GetActorScale3D().Equals(FVector(2)));
	if (TestEqual(TEXT("Transform result"), Changed.Entries.Num(), 1))
	{
		TestEqual(TEXT("Previous transform returned"), Changed.Entries[0]->AsObject()->GetStringField(TEXT("OldLocation")), FString(TEXT("7.0,8.0,9.0")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewDirtyLevelTest, "NexusLink.Review.DirtyLevelProtection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewDirtyLevelTest::RunTest(const FString& Parameters)
{
	// 暂存已有脏标记，让断言只由测试的非当前地图/外部 Actor 包触发。
	TArray<UPackage*> ExistingDirty;
	FEditorFileUtils::GetDirtyWorldPackages(ExistingDirty);
	for (UPackage* Package : ExistingDirty) Package->SetDirtyFlag(false);
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/DirtyLevel_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* OtherWorld = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("DirtyLevel"), Package);
	UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
	ON_SCOPE_EXIT
	{
		Package->SetDirtyFlag(false);
		OtherWorld->DestroyWorld(false);
		for (UPackage* Existing : ExistingDirty) Existing->SetDirtyFlag(true);
	};
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), TEXT("/Engine/Maps/Entry"));
	Package->SetDirtyFlag(true);
	TestTrue(TEXT("Dirty non-current level blocks map switch"), ReviewCall(TEXT("ControlEditorLevel"), Args).HasErrors());
	TestTrue(TEXT("Rejected switch preserves world"), GEditor->GetEditorWorldContext().World() == CurrentWorld);
	TestTrue(TEXT("Rejected switch preserves dirty flag"), Package->IsDirty());
#if NX_UE_AT_LEAST(5, 0)
	AActor* ExternalActor = OtherWorld->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("External Actor"), ExternalActor)) return false;
	UPackage* ExternalPackage = CreatePackage(*(Package->GetName() + TEXT("_Actor")));
	ExternalActor->SetExternalPackage(ExternalPackage);
	ExternalPackage->SetDirtyFlag(true);
	Package->SetDirtyFlag(false);
	TestTrue(TEXT("Dirty external Actor blocks switch with clean world"), ReviewCall(TEXT("ControlEditorLevel"), Args).HasErrors());
	TestTrue(TEXT("External dirty flag preserved"), ExternalPackage->IsDirty());
	TestTrue(TEXT("External rejection preserves world"), GEditor->GetEditorWorldContext().World() == CurrentWorld);
	ExternalPackage->SetDirtyFlag(false);
	ExternalActor->SetExternalPackage(nullptr);
#endif
	return true;
}
#endif
