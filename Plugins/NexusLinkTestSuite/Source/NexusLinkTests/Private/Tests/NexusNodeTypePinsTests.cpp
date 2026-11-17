// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimBlueprintGeneratedClass.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "EdGraph/EdGraph.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "GameFramework/Actor.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/ScopeExit.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusNodeTypePinsTest, "NexusLink.Blueprint.NodeTypePinsReadOnly", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusNodeTypePinsTest::RunTest(const FString& Parameters)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetAssetBlueprint"));
	if (!TestNotNull(TEXT("蓝图读取能力已注册"), Record)) return false;
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/NodeTypePins_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	UBlueprint* ActorBlueprint = FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package, TEXT("ActorBlueprint"), BPTYPE_Normal,
		UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	UBlueprint* AnimBlueprint = FKismetEditorUtilities::CreateBlueprint(UAnimInstance::StaticClass(), Package, TEXT("AnimBlueprint"), BPTYPE_Normal,
		UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass());
	if (!TestNotNull(TEXT("Actor 蓝图测试对象"), ActorBlueprint) || !TestNotNull(TEXT("动画蓝图测试对象"), AnimBlueprint)) return false;
	struct FFunctionCase { UClass* Owner; const TCHAR* Name; const TCHAR* Pin; };
	const TCHAR* MeshSetter = USkeletalMeshComponent::StaticClass()->FindFunctionByName(TEXT("SetSkeletalMesh")) ? TEXT("SetSkeletalMesh") : TEXT("SetSkeletalMeshAsset");
	const FFunctionCase Functions[] = {
		{USkeletalMeshComponent::StaticClass(), TEXT("OverrideAnimationData"), TEXT("InAnimToPlay")},
		{USkeletalMeshComponent::StaticClass(), MeshSetter, TEXT("NewMesh")},
		{UKismetMathLibrary::StaticClass(), TEXT("EqualEqual_IntInt"), TEXT("ReturnValue")}
	};
	for (UBlueprint* Blueprint : {ActorBlueprint, AnimBlueprint})
	{
		UEdGraph* Graph = nullptr;
		for (UEdGraph* Candidate : Blueprint->UbergraphPages) if (Candidate && Candidate->GetName() == TEXT("EventGraph")) Graph = Candidate;
		if (!TestNotNull(TEXT("EventGraph 测试上下文"), Graph)) return false;
		const int32 OriginalNodeCount = Graph->Nodes.Num();
		const EBlueprintStatus OriginalStatus = Blueprint->Status;
		Package->SetDirtyFlag(false);
		auto Args = MakeShared<FJsonObject>();
		Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
		Args->SetStringField(TEXT("GraphName"), Graph->GetName());
		Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("NodeTypePins"))});
		for (const FFunctionCase& Function : Functions)
		{
			Args->SetStringField(TEXT("FunctionName"), Function.Name);
			Args->SetStringField(TEXT("FunctionClass"), Function.Owner->GetPathName());
			const FCapabilityResult Read = Record->Instance->Run(Args);
			if (!TestFalse(FString::Printf(TEXT("%s/%s 查询成功"), *Blueprint->GetName(), Function.Name), Read.HasErrors())
				|| !TestEqual(TEXT("返回一个资产结果"), Read.Entries.Num(), 1)) return false;
			const TArray<TSharedPtr<FJsonValue>>* Pins = nullptr;
			if (!TestTrue(TEXT("返回函数引脚列表"), Read.Entries[0]->AsObject()->TryGetArrayField(TEXT("NodeTypePins"), Pins))) return false;
			TestTrue(TEXT("引脚列表非空"), Pins->Num() > 0);
			TestTrue(FString::Printf(TEXT("返回关键引脚 %s"), Function.Pin), Pins->ContainsByPredicate([&](const TSharedPtr<FJsonValue>& Pin)
			{
				return Pin.IsValid() && Pin->Type == EJson::Object && Pin->AsObject()->GetStringField(TEXT("PinName")) == Function.Pin;
			}));
			TestEqual(TEXT("查询不向源图添加节点"), Graph->Nodes.Num(), OriginalNodeCount);
			TestTrue(TEXT("查询保持蓝图编译状态"), Blueprint->Status == OriginalStatus);
			TestFalse(TEXT("查询保持包清洁"), Package->IsDirty());
		}
		Args->SetStringField(TEXT("FunctionClass"), USkeletalMeshComponent::StaticClass()->GetPathName());
		TestTrue(TEXT("显式所属类缺少函数时不误取其他类函数"), Record->Instance->Run(Args).HasErrors());
		Args->SetStringField(TEXT("FunctionClass"), TEXT("/Script/Engine.MissingFunctionOwner"));
		TestTrue(TEXT("无效显式所属类不退回全局函数"), Record->Instance->Run(Args).HasErrors());
		Args->SetStringField(TEXT("GraphName"), TEXT("MissingGraph"));
		TestTrue(TEXT("无效图上下文返回错误"), Record->Instance->Run(Args).HasErrors());
		Args->RemoveField(TEXT("GraphName"));
		TestTrue(TEXT("缺失图上下文返回错误"), Record->Instance->Run(Args).HasErrors());
		TestEqual(TEXT("拒绝查询不添加节点"), Graph->Nodes.Num(), OriginalNodeCount);
		TestTrue(TEXT("拒绝查询保持编译状态"), Blueprint->Status == OriginalStatus);
		TestFalse(TEXT("拒绝查询保持包清洁"), Package->IsDirty());
	}
	return true;
}
#endif
