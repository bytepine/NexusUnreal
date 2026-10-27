// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#include "Utils/NexusBlackboardUtils.h"
#include "BehaviorTree/BlackboardData.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBlackboardTypedTest, "NexusLink.AI.Blackboard.TypedInherited",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusBlackboardTypedTest::RunTest(const FString& Parameters)
{
	UBlackboardData* Parent = NewObject<UBlackboardData>();
	FBlackboardEntry Condition;
	Condition.EntryName = TEXT("CanRun");
	Condition.KeyType = NewObject<UBlackboardKeyType_Bool>(Parent);
	Parent->Keys.Add(Condition);
	Parent->UpdateKeyIDs();
	UBlackboardData* Child = NewObject<UBlackboardData>();
	Child->Keys.Reset();
	Child->Parent = Parent;
	FBlackboardEntry Local;
	Local.EntryName = TEXT("Message");
	Local.KeyType = NewObject<UBlackboardKeyType_String>(Child);
	Child->Keys.Add(Local);
	Child->UpdateKeyIDs();
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	World->CreateAISystem();
	AActor* Owner = World->SpawnActor<AActor>();
	UBlackboardComponent* Board = NewObject<UBlackboardComponent>(Owner);
	TestTrue(TEXT("Initialize inherited data"), Board->InitializeBlackboard(*Child));
	const auto KeyId = Board->GetKeyID(TEXT("CanRun"));
	TestTrue(TEXT("Parent key retained"), Child->GetKey(KeyId) != nullptr && static_cast<uint16>(KeyId) < static_cast<uint16>(Child->GetFirstKeyID()));
	Board->SetValueAsBool(TEXT("CanRun"), true);
	FJsonObject Result;
	FNexusBlackboardUtils::WriteTyped(Board, TEXT("CanRun"), Condition.KeyType, Result);
	TestEqual(TEXT("Native type"), Result.GetStringField(TEXT("TypeName")), FString(TEXT("Bool")));
	TestTrue(TEXT("Typed inherited value"), Result.GetBoolField(TEXT("TypedValue")));
	Board->SetValueAsString(TEXT("Message"), TEXT("hello"));
	FNexusBlackboardUtils::WriteTyped(Board, TEXT("Message"), Local.KeyType, Result);
	TestEqual(TEXT("Typed local value"), Result.GetStringField(TEXT("TypedValue")), FString(TEXT("hello")));
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBlackboardTypeValidationTest, "NexusLink.AI.Blackboard.InvalidTypes",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusBlackboardTypeValidationTest::RunTest(const FString& Parameters)
{
	TestTrue(TEXT("Bool"), FNexusBlackboardUtils::IsValidScalar(TEXT("Bool"), TEXT("false")));
	TestFalse(TEXT("Invalid Bool"), FNexusBlackboardUtils::IsValidScalar(TEXT("Bool"), TEXT("maybe")));
	TestFalse(TEXT("Int trailing junk"), FNexusBlackboardUtils::IsValidScalar(TEXT("Int"), TEXT("42x")));
	TestFalse(TEXT("Int overflow"), FNexusBlackboardUtils::IsValidScalar(TEXT("Int"), TEXT("2147483648")));
	TestFalse(TEXT("Enum overflow"), FNexusBlackboardUtils::IsValidScalar(TEXT("Enum"), TEXT("256")));
	TestFalse(TEXT("Float nonfinite"), FNexusBlackboardUtils::IsValidScalar(TEXT("Float"), TEXT("nan")));
	TestFalse(TEXT("Float overflow"), FNexusBlackboardUtils::IsValidScalar(TEXT("Float"), TEXT("1e80")));
	return true;
}
